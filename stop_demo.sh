#!/bin/bash

# Oil & Gas Field Operations - Redis Enterprise Demo Stop Script
# This script stops all demo processes cleanly

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🛑 Stopping Oil & Gas Field Operations Demo${NC}"
echo -e "${BLUE}============================================${NC}"
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

# Function to kill process safely
kill_process() {
    local pid=$1
    local name=$2
    
    if kill -0 "$pid" 2>/dev/null; then
        print_info "Stopping $name (PID: $pid)..."
        kill "$pid" 2>/dev/null || true
        
        # Wait for process to stop
        local attempts=0
        while kill -0 "$pid" 2>/dev/null && [ $attempts -lt 10 ]; do
            sleep 1
            attempts=$((attempts + 1))
        done
        
        if kill -0 "$pid" 2>/dev/null; then
            print_warning "Force killing $name (PID: $pid)..."
            kill -9 "$pid" 2>/dev/null || true
        fi
        
        print_status "$name stopped"
    else
        print_info "$name (PID: $pid) was not running"
    fi
}

# Function to kill processes on port
kill_port() {
    local port=$1
    local service_name=$2
    
    print_info "Checking for processes on port $port..."
    
    local pids=$(lsof -ti:$port 2>/dev/null || true)
    if [ -n "$pids" ]; then
        print_info "Killing $service_name processes on port $port..."
        echo "$pids" | xargs kill -9 2>/dev/null || true
        print_status "$service_name processes on port $port stopped"
    else
        print_info "No processes found on port $port"
    fi
}

# Stop processes using saved PIDs
if [ -f "demo_pids.txt" ]; then
    print_info "Reading saved process IDs..."
    
    read -r backend_pid simulator_pid < demo_pids.txt
    
    if [ -n "$backend_pid" ] && [ "$backend_pid" != "0" ]; then
        kill_process "$backend_pid" "Backend Server"
    fi
    
    if [ -n "$simulator_pid" ] && [ "$simulator_pid" != "0" ]; then
        kill_process "$simulator_pid" "Data Simulator"
    fi
    
    # Remove PID file
    rm -f demo_pids.txt
    print_status "PID file removed"
else
    print_warning "No PID file found, attempting to stop by port..."
fi

# Kill any remaining processes on port 5001
kill_port 5001 "Backend Server"

# Kill any Python processes that might be running the demo
print_info "Checking for remaining demo processes..."

# Look for specific demo processes
demo_processes=$(ps aux | grep -E "(app\.py|field_data_simulator\.py)" | grep -v grep | awk '{print $2}' || true)

if [ -n "$demo_processes" ]; then
    print_info "Found remaining demo processes, stopping them..."
    echo "$demo_processes" | xargs kill -9 2>/dev/null || true
    print_status "Remaining demo processes stopped"
else
    print_info "No remaining demo processes found"
fi

# Clean up log files (optional)
echo ""
print_info "Cleaning up log files..."

if [ -f "backend.log" ]; then
    rm -f backend.log
    print_status "Backend log removed"
fi

if [ -f "simulator.log" ]; then
    rm -f simulator.log
    print_status "Simulator log removed"
fi

# Optional: Clear Redis data
echo ""
read -p "Do you want to clear Redis data? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    print_info "Clearing Redis data..."

    # Load environment variables from .env file
    if [ -f .env ]; then
        export $(cat .env | grep -v '^#' | xargs)

        if redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" -a "$REDIS_PASSWORD" FLUSHDB >/dev/null 2>&1; then
            print_status "Redis data cleared"
        else
            print_error "Failed to clear Redis data"
        fi
    else
        print_warning ".env file not found - skipping Redis data clear"
    fi
else
    print_info "Redis data preserved"
fi

echo ""
echo -e "${GREEN}🎉 Demo stopped successfully!${NC}"
echo -e "${GREEN}=============================${NC}"
echo ""
echo -e "${BLUE}To restart the demo, run: ./start_demo.sh${NC}"
echo ""
