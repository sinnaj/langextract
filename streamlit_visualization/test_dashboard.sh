#!/bin/bash

# Quick test script for the Streamlit visualization dashboard
# This script tests that the dashboard can be started successfully

echo "🔍 Testing LangExtract Streamlit Dashboard"
echo "=========================================="

# Check if we're in the right directory
if [ ! -f "app.py" ]; then
    echo "❌ Error: Please run this script from the streamlit_visualization directory"
    exit 1
fi

# Check if streamlit is installed
if ! python -c "import streamlit" 2>/dev/null; then
    echo "📦 Installing required dependencies..."
    pip install -r requirements.txt
fi

echo "✅ Dependencies installed"

# Check if data files exist
echo "🔍 Checking for data files..."
if find ../output_runs -name "combined_extractions.json" 2>/dev/null | head -1 | grep -q .; then
    echo "✅ Found combined_extractions.json files"
else
    echo "⚠️  No combined_extractions.json files found in output_runs"
    echo "   You can still test by uploading a file through the dashboard"
fi

echo ""
echo "🚀 Starting Streamlit dashboard..."
echo "   Dashboard will be available at: http://localhost:8501"
echo "   Press Ctrl+C to stop"
echo ""

# Start streamlit
python -m streamlit run app.py