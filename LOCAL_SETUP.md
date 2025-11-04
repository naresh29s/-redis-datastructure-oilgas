# 🛢️ Oil & Gas Field Operations Demo - Local Setup

## Quick Start Guide

### Prerequisites

1. **Redis Server** - Running on localhost:6379
   ```bash
   # Install Redis (macOS)
   brew install redis
   
   # Start Redis
   redis-server
   # OR
   brew services start redis
   
   # Verify Redis is running
   redis-cli ping
   # Should return: PONG
   ```

2. **Python 3.7+** with pip
   ```bash
   python3 --version
   pip3 --version
   ```

### 🚀 Run the Demo

1. **Configure your Redis credentials:**
   ```bash
   # Copy the environment template
   cp .env.example .env

   # Edit .env with your Redis credentials
   nano .env
   ```

2. **Start the complete demo:**
   ```bash
   ./start_demo.sh
   ```

3. **Access the dashboard:**
   - **Frontend Dashboard:** http://localhost:5001
   - **Backend API:** http://localhost:5001/api
   - **Health Check:** http://localhost:5001/health

4. **Stop the demo:**
   ```bash
   ./stop_demo.sh
   ```

### 📊 What You'll See

The demo automatically:
- ✅ Connects to your local Redis server
- ✅ Starts generating realistic oil & gas field data
- ✅ Launches the web dashboard
- ✅ Opens your browser to the dashboard

### 🎯 Demo Features

1. **🗺️ Geospatial Asset Tracking**
   - Interactive map showing field assets (rigs, trucks, equipment)
   - Real-time location updates
   - Asset status monitoring

2. **📡 Edge-to-Core Streaming**
   - Live sensor data from field equipment
   - Temperature, pressure, flow rate, vibration monitoring
   - Redis Streams for real-time data buffering

3. **📊 Real-Time Operational Dashboard**
   - Live KPIs and metrics
   - Active alerts and warnings
   - Production monitoring

### 🔧 Manual Setup (Alternative)

If you prefer to run components individually:

1. **Install dependencies:**
   ```bash
   pip3 install -r backend/requirements.txt
   ```

2. **Start data simulator:**
   ```bash
   cd simulators
   python3 field_data_simulator.py
   ```

3. **Start backend API (new terminal):**
   ```bash
   cd backend
   python3 app.py
   ```

4. **Start frontend (new terminal):**
   ```bash
   cd frontend
   python3 -m http.server 8080
   ```

5. **Open browser:**
   ```
   http://localhost:8080
   ```

### 📝 Logs and Troubleshooting

- **Log files:** `logs/` directory
  - `simulator.log` - Data generation logs
  - `backend.log` - API server logs
  - `frontend.log` - Web server logs

- **Common issues:**
  - **Redis not running:** Start with `redis-server`
  - **Port conflicts:** Change ports in scripts if needed
  - **Python dependencies:** Run `pip3 install -r backend/requirements.txt`

### 🎬 Demo Script (15-20 minutes)

1. **Introduction (2 min)**
   - Show dashboard overview
   - Explain oil & gas field operations context

2. **Geospatial Tracking (5 min)**
   - Point out assets on map
   - Show real-time movement of service trucks
   - Demonstrate nearby asset search

3. **Streaming Data (5 min)**
   - Show live sensor readings
   - Point out different sensor types
   - Explain Redis Streams buffering

4. **Operational Dashboard (5 min)**
   - Review KPIs and metrics
   - Show active alerts
   - Demonstrate real-time updates

5. **Redis Enterprise Value (3 min)**
   - High availability and clustering
   - Sub-millisecond latency
   - Geospatial and streaming capabilities

### 🛠️ Customization

- **Change location:** Edit `BASE_LAT` and `BASE_LON` in `simulators/field_data_simulator.py`
- **Add assets:** Modify the `assets` list in the simulator
- **Adjust data rates:** Change sleep intervals in simulator threads
- **Modify UI:** Edit `frontend/index.html`

### 🔄 Redis Data Structure

The demo uses these Redis data structures:
- **Geospatial:** `assets:locations` - Asset positions
- **Hashes:** `asset:{id}` - Asset details
- **Streams:** `sensor:stream:{id}` - Sensor data
- **Hashes:** `sensor:latest:{id}` - Latest readings
- **Sorted Sets:** `alerts:active` - Active alerts
- **Strings:** `metrics:*` - Dashboard KPIs

### 📞 Support

For issues or questions:
- Check log files in `logs/` directory
- Verify Redis connection with `redis-cli ping`
- Ensure all ports (5000, 8080, 6379) are available
