#!/bin/bash
# Test script to verify memory optimization fixes

echo "=========================================="
echo "MEMORY FIX VERIFICATION"
echo "=========================================="

echo ""
echo "1. Checking RAM availability..."
free -h | grep "Mem:"

echo ""
echo "2. Checking Python processes..."
ps aux | grep python | grep -v grep | wc -l
ps aux | grep python | grep -v grep | awk '{print $6}' | awk '{sum+=$1} END {print "Total Python memory: " sum/1024 "MB"}'

echo ""
echo "3. Checking guardrail.py for memory cleanup..."
if grep -q "gc.collect()" src/perception/guardrail.py; then
    echo "✓ gc.collect() found in guardrail.py"
else
    echo "✗ gc.collect() NOT found in guardrail.py"
fi

echo ""
echo "4. Checking audits.py for CUDA cleanup..."
if grep -q "torch.cuda.empty_cache()" src/routes/audits.py; then
    echo "✓ torch.cuda.empty_cache() found in audits.py"
else
    echo "✗ torch.cuda.empty_cache() NOT found in audits.py"
fi

echo ""
echo "5. Checking for garbage collection import..."
if grep -q "import gc" src/routes/audits.py; then
    echo "✓ gc module imported"
else
    echo "✗ gc module NOT imported"
fi

echo ""
echo "=========================================="
echo "NEXT STEPS:"
echo "=========================================="
echo "1. Restart the backend:"
echo "   kill -9 \$(lsof -ti :8000)"
echo "   python src/main.py"
echo ""
echo "2. Run upload tests:"
echo "   for i in {1..10}; do curl -X POST http://localhost:8000/audits ...; done"
echo ""
echo "3. Monitor output for memory cleanup logs:"
echo "   [MEM] CUDA cache cleared"
echo "   [MEM] Garbage collection triggered"
echo ""
echo "=========================================="
