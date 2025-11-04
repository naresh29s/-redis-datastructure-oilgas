#!/bin/bash

# Oil & Gas Field Operations - Redis Enterprise Demo Startup Script
# This script automates the complete demo initialization process

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Load environment variables from .env file
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
    echo -e "${GREEN}✅ Loaded environment variables from .env${NC}"
else
    echo -e "${RED}❌ Error: .env file not found!${NC}"
    echo -e "${YELLOW}Please copy .env.example to .env and configure your Redis credentials:${NC}"
    echo -e "  cp .env.example .env"
    echo -e "  # Then edit .env with your Redis credentials"
    exit 1
fi

# Demo configuration
BACKEND_PORT="${BACKEND_PORT:-5001}"
DEMO_URL="http://localhost:${BACKEND_PORT}"

echo -e "${BLUE}🛢️  Oil & Gas Field Operations - Redis Enterprise Demo${NC}"
echo -e "${BLUE}================================================================${NC}"
echo ""

# Function to print status messages
print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check if port is available
check_port() {
    if lsof -Pi :$1 -sTCP:LISTEN -t >/dev/null 2>&1; then
        return 1  # Port is in use
    else
        return 0  # Port is available
    fi
}

# Function to kill process on port
kill_port() {
    local port=$1
    print_info "Killing any existing process on port $port..."
    lsof -ti:$port | xargs kill -9 2>/dev/null || true
    sleep 2
}

# Function to wait for service to be ready
wait_for_service() {
    local url=$1
    local service_name=$2
    local max_attempts=30
    local attempt=1
    
    print_info "Waiting for $service_name to be ready..."
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s "$url" >/dev/null 2>&1; then
            print_status "$service_name is ready!"
            return 0
        fi
        
        echo -n "."
        sleep 2
        attempt=$((attempt + 1))
    done
    
    print_error "$service_name failed to start within $((max_attempts * 2)) seconds"
    return 1
}

# Function to verify API endpoint
verify_api() {
    local endpoint=$1
    local description=$2
    
    if curl -s "$endpoint" | python3 -c "import sys, json; data=json.load(sys.stdin); exit(0 if data.get('success') else 1)" 2>/dev/null; then
        print_status "$description: Working"
        return 0
    else
        print_error "$description: Failed"
        return 1
    fi
}

echo -e "${YELLOW}🔍 Checking Prerequisites...${NC}"

# Check required commands
MISSING_DEPS=()

if ! command_exists python3; then
    MISSING_DEPS+=("python3")
fi

if ! command_exists pip; then
    MISSING_DEPS+=("pip")
fi

if ! command_exists curl; then
    MISSING_DEPS+=("curl")
fi

if ! command_exists redis-cli; then
    MISSING_DEPS+=("redis-cli")
fi

if [ ${#MISSING_DEPS[@]} -ne 0 ]; then
    print_error "Missing required dependencies: ${MISSING_DEPS[*]}"
    echo "Please install the missing dependencies and try again."
    exit 1
fi

print_status "All required dependencies are installed"

# Check Python packages
echo ""
echo -e "${YELLOW}📦 Checking Python Dependencies...${NC}"

PYTHON_DEPS=("flask" "redis" "requests")
MISSING_PYTHON_DEPS=()

for dep in "${PYTHON_DEPS[@]}"; do
    if ! python3 -c "import $dep" 2>/dev/null; then
        MISSING_PYTHON_DEPS+=("$dep")
    fi
done

if [ ${#MISSING_PYTHON_DEPS[@]} -ne 0 ]; then
    print_warning "Installing missing Python packages: ${MISSING_PYTHON_DEPS[*]}"
    pip install "${MISSING_PYTHON_DEPS[@]}"
fi

print_status "All Python dependencies are available"

# Check if port is available
echo ""
echo -e "${YELLOW}🔌 Checking Port Availability...${NC}"

if ! check_port $BACKEND_PORT; then
    print_warning "Port $BACKEND_PORT is in use. Attempting to free it..."
    kill_port $BACKEND_PORT
    
    if ! check_port $BACKEND_PORT; then
        print_error "Unable to free port $BACKEND_PORT. Please manually stop the process and try again."
        exit 1
    fi
fi

print_status "Port $BACKEND_PORT is available"

# Test Redis connection
echo ""
echo -e "${YELLOW}🔗 Testing Redis Connection...${NC}"

if redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" -a "$REDIS_PASSWORD" ping >/dev/null 2>&1; then
    print_status "Redis connection successful"
else
    print_error "Cannot connect to Redis Cloud. Please check your connection and credentials."
    exit 1
fi

# Clear Redis data for fresh start
echo ""
echo -e "${YELLOW}🧹 Clearing Redis Data for Fresh Start...${NC}"

redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" -a "$REDIS_PASSWORD" FLUSHDB >/dev/null 2>&1
print_status "Redis database cleared"

# Create search index
echo ""
echo -e "${YELLOW}🔍 Creating Search Index...${NC}"

redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" -a "$REDIS_PASSWORD" \
    FT.CREATE idx:assets ON JSON PREFIX 1 asset: SCHEMA \
    '$.asset.id' AS id TAG \
    '$.asset.name' AS name TEXT \
    '$.asset.type' AS type TAG \
    '$.asset.model.manufacturer' AS manufacturer TAG \
    '$.asset.status.state' AS status TAG \
    '$.asset.location.field' AS field TAG \
    '$.asset.location.coordinates[0]' AS longitude NUMERIC \
    '$.asset.location.coordinates[1]' AS latitude NUMERIC >/dev/null 2>&1

print_status "Search index created"

# Start backend server
echo ""
echo -e "${YELLOW}🚀 Starting Backend Server...${NC}"

cd backend
nohup python3 app.py > ../backend.log 2>&1 &
BACKEND_PID=$!
cd ..

# Wait for backend to be ready
if wait_for_service "$DEMO_URL/api/dashboard/kpis" "Backend Server"; then
    print_status "Backend server started (PID: $BACKEND_PID)"
else
    print_error "Backend server failed to start"
    kill $BACKEND_PID 2>/dev/null || true
    exit 1
fi

# Start data simulator
echo ""
echo -e "${YELLOW}📊 Starting Data Simulator...${NC}"

cd simulators
nohup python3 field_data_simulator.py > ../simulator.log 2>&1 &
SIMULATOR_PID=$!
cd ..

print_status "Data simulator started (PID: $SIMULATOR_PID)"

# Wait a moment for data to be populated
print_info "Waiting for initial data population..."
sleep 10

# Verify all services
echo ""
echo -e "${YELLOW}✅ Verifying Demo Services...${NC}"

VERIFICATION_FAILED=false

# Test Dashboard API
if ! verify_api "$DEMO_URL/api/dashboard/kpis" "Dashboard API"; then
    VERIFICATION_FAILED=true
fi

# Test Sessions API
if ! verify_api "$DEMO_URL/api/sessions" "Sessions API"; then
    VERIFICATION_FAILED=true
fi

# Test Search API
if ! verify_api "$DEMO_URL/api/search/assets?q=*&limit=3" "Search API"; then
    VERIFICATION_FAILED=true
fi

# Test Frontend
if curl -s "$DEMO_URL/" | grep -q "Oil & Gas Field Operations"; then
    print_status "Frontend: Serving correctly"
else
    print_error "Frontend: Failed to load"
    VERIFICATION_FAILED=true
fi

if [ "$VERIFICATION_FAILED" = true ]; then
    print_error "Some services failed verification. Check the logs for details."
    echo "Backend log: tail -f backend.log"
    echo "Simulator log: tail -f simulator.log"
    exit 1
fi

# Success message
echo ""
echo -e "${GREEN}🎉 DEMO SUCCESSFULLY STARTED!${NC}"
echo -e "${GREEN}================================${NC}"
echo ""
echo -e "${BLUE}📊 Demo URL: ${DEMO_URL}${NC}"
echo -e "${BLUE}🔧 Backend PID: ${BACKEND_PID}${NC}"
echo -e "${BLUE}📈 Simulator PID: ${SIMULATOR_PID}${NC}"
echo ""
echo -e "${YELLOW}📋 Quick Verification Commands:${NC}"
echo "curl -s \"$DEMO_URL/api/dashboard/kpis\" | python3 -c \"import sys, json; data=json.load(sys.stdin); print('KPIs:', len(data.get('kpis', [])))\""
echo "curl -s \"$DEMO_URL/api/sessions\" | python3 -c \"import sys, json; data=json.load(sys.stdin); print('Sessions:', len(data.get('sessions', [])))\""
echo "curl -s \"$DEMO_URL/api/search/assets?q=*&limit=3\" | python3 -c \"import sys, json; data=json.load(sys.stdin); print('Assets:', data.get('total', 0))\""
echo ""
echo -e "${YELLOW}📝 Logs:${NC}"
echo "Backend: tail -f backend.log"
echo "Simulator: tail -f simulator.log"
echo ""
echo -e "${YELLOW}🛑 To Stop Demo:${NC}"
echo "kill $BACKEND_PID $SIMULATOR_PID"
echo ""

# Save PIDs for easy cleanup
echo "$BACKEND_PID $SIMULATOR_PID" > demo_pids.txt

# Try to open browser (optional)
if command_exists open; then
    print_info "Opening demo in browser..."
    open "$DEMO_URL" 2>/dev/null || true
elif command_exists xdg-open; then
    print_info "Opening demo in browser..."
    xdg-open "$DEMO_URL" 2>/dev/null || true
fi

echo -e "${GREEN}🚀 Demo is ready for presentation!${NC}"
