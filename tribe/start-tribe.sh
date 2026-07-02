#!/bin/bash
# Start the Tribe Memory System
# Run this to ensure all memory services are online

echo "🧠 Starting Tribe Memory System..."

# Check if tribe-memory is running
if ! pm2 list | grep -q "tribe-memory"; then
    echo "Starting tribe-memory..."
    pm2 start /opt/alloyscape/services/graphiti/LAUNCHER --name tribe-memory
else
    echo "✓ tribe-memory already running"
fi

# Check health
echo ""
echo "Checking health..."
curl -s http://127.0.0.1:8472/health | python3 -m json.tool 2>/dev/null || curl -s http://127.0.0.1:8472/health

echo ""
echo "📊 PM2 Status:"
pm2 list | grep -E "(tribe-memory|forge|alloy|iris|joe|josie|ponte)"

echo ""
echo "✓ Tribe memory is ready"
echo ""
echo "Quick commands:"
echo "  node /opt/alloyscape/tribe/memory/forge-memory.mjs 'what I did' build"
echo "  node /opt/alloyscape/tribe/memory/remember.mjs recall 'graphiti' 5"
echo "  cat /opt/alloyscape/INDEX.md"
