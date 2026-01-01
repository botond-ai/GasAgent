#!/bin/bash

# PORT AUDIT SCRIPT
# Ellenőrzi, hogy csak a szükséges portok (8000, 5173) vannak használatban

echo "🔍 Port Audit - RAG Agent Start-Dev Script"
echo "==========================================="
echo ""

echo "✅ Elvárt portok (aktívnak kell lenni):"
echo "   • 8000 (Backend API)"
echo "   • 5173 (Frontend Dev Server)"
echo ""

echo "❌ Felesleges portok (tiltottak):"
echo "   • 3000 (régi)"
echo "   • 3001 (régi)"
echo "   • 3002 (régi)"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "PORT AUDIT EREDMÉNY"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Ellenőrizzük a szükséges portokat
for port in 8000 5173; do
    if lsof -i :$port 2>/dev/null | grep -v COMMAND > /dev/null; then
        echo "✅ Port $port: AKTÍV"
        lsof -i :$port 2>/dev/null | grep -v COMMAND | awk '{print "   Proces: " $1 " (PID: " $2 ")"}'
    else
        echo "⚠️  Port $port: SZABAD (kell hogy aktív legyen!)"
    fi
done

echo ""

# Ellenőrizzük a tiltott portokat
for port in 3000 3001 3002; do
    if lsof -i :$port 2>/dev/null | grep -v COMMAND > /dev/null; then
        echo "❌ Port $port: FOGLALT (KÉK LENNI!)"
        lsof -i :$port 2>/dev/null | grep -v COMMAND | awk '{print "   Proces: " $1 " (PID: " $2 ")"}'
    else
        echo "✅ Port $port: SZABAD (jó)"
    fi
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
