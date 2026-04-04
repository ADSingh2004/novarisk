#!/bin/bash

# NovaRisk ESG - API Batch Test Script
# ====================================
# Tests all 8 validation locations via the REST API
#
# Usage:
#   bash test_all_locations.sh
#   bash test_all_locations.sh --export results.json
#
# Prerequisites:
#   - Backend running on localhost:8000
#   - Redis running
#   - jq installed (optional, for pretty formatting)

set -e

BASE_URL="${API_URL:-http://localhost:8000/api/v1/facility/analyze}"
EXPORT_FILE="${1:-}"
USE_JQ=$(command -v jq &> /dev/null && echo true || echo false)

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Helper function to print colored status
print_status() {
    local status=$1
    local message=$2
    case $status in
        "PASS")
            echo -e "${GREEN}✓ $message${NC}"
            ;;
        "FAIL")
            echo -e "${RED}✗ $message${NC}"
            ;;
        "INFO")
            echo -e "${YELLOW}ℹ $message${NC}"
            ;;
    esac
}

echo "=========================================="
echo "NovaRisk ESG - Batch API Test"
echo "=========================================="
echo ""

# Check if API is accessible
print_status "INFO" "Testing API connectivity..."
if ! curl -s "${BASE_URL}?latitude=0&longitude=0" > /dev/null 2>&1; then
    print_status "FAIL" "Cannot reach API at $BASE_URL"
    print_status "INFO" "Make sure backend is running: uvicorn app.main:app --reload"
    exit 1
fi
print_status "PASS" "API is accessible"
echo ""

# Array of test locations
declare -A LOCATIONS=(
    ["sao_paulo"]="São Paulo, Brazil|-23.55|-46.65"
    ["new_delhi"]="New Delhi, India|28.70|77.10"
    ["jakarta"]="Jakarta, Indonesia|-6.21|106.85"
    ["los_angeles"]="Los Angeles, USA|34.05|-118.24"
    ["cerrado"]="Cerrado, Brazil|-10.2|-55.5"
    ["shenyang"]="Shenyang, China|41.80|123.92"
    ["kumasi"]="Kumasi, Ghana|6.63|-1.63"
    ["bangalore"]="Bangalore, India|12.97|77.59"
)

RESULTS=()
COUNT=0
PASSED=0
PARTIAL=0
FAILED=0
TOTAL=${#LOCATIONS[@]}

# Test each location
for key in "${!LOCATIONS[@]}"; do
    COUNT=$((COUNT + 1))
    IFS='|' read -r name lat lon <<< "${LOCATIONS[$key]}"
    
    echo "[$COUNT/$TOTAL] Testing: $name ($lat, $lon)"
    
    # Make API call
    RESPONSE=$(curl -s "${BASE_URL}?latitude=${lat}&longitude=${lon}&radius_km=5.0")
    
    # Extract metrics
    DEFORESTATION=$(echo "$RESPONSE" | grep -o '"deforestation_risk":[^,}]*' | grep -o '[0-9.]*' || echo "0")
    WATER=$(echo "$RESPONSE" | grep -o '"water_stress_proxy":[^,}]*' | grep -o '[0-9.]*' || echo "0")
    UHI=$(echo "$RESPONSE" | grep -o '"heat_island_index":[^,}]*' | grep -o '[0-9.]*' || echo "0")
    
    # Check if values are valid
    if [ -z "$DEFORESTATION" ] || [ -z "$WATER" ] || [ -z "$UHI" ]; then
        print_status "FAIL" "Failed to parse response"
        FAILED=$((FAILED + 1))
    else
        # Convert to floats for comparison
        DEFO_INT=$(echo "$DEFORESTATION" | cut -d. -f1)
        WATER_INT=$(echo "$WATER" | cut -d. -f1)
        UHI_INT=$(echo "$UHI" | cut -d. -f1)
        
        # Count how many metrics are non-zero
        NON_ZERO=0
        [ "$DEFO_INT" != "0" ] && NON_ZERO=$((NON_ZERO + 1))
        [ "$WATER_INT" != "0" ] && NON_ZERO=$((NON_ZERO + 1))
        [ "$UHI_INT" != "0" ] && NON_ZERO=$((NON_ZERO + 1))
        
        if [ $NON_ZERO -eq 3 ]; then
            print_status "PASS" "Deforestation: $DEFORESTATION, Water: $WATER, UHI: $UHI"
            PASSED=$((PASSED + 1))
        elif [ $NON_ZERO -gt 0 ]; then
            print_status "PASS" "Deforestation: $DEFORESTATION, Water: $WATER, UHI: $UHI (partial)"
            PARTIAL=$((PARTIAL + 1))
        else
            print_status "FAIL" "All metrics returned 0"
            FAILED=$((FAILED + 1))
        fi
    fi
    
    # Store result
    RESULT="{\"location\": \"$name\", \"lat\": $lat, \"lon\": $lon, \"deforestation\": $DEFORESTATION, \"water_stress\": $WATER, \"uhi\": $UHI}"
    RESULTS+=("$RESULT")
    
    echo ""
done

# Summary
echo "=========================================="
echo "SUMMARY"
echo "=========================================="
echo "Total Tests:    $TOTAL"
echo -e "Passed:         ${GREEN}$PASSED${NC}"
echo -e "Partial:        ${YELLOW}$PARTIAL${NC}"
echo -e "Failed:         ${RED}$FAILED${NC}"
PASS_RATE=$(echo "scale=1; ($PASSED * 100) / $TOTAL" | bc 2>/dev/null || echo "?")
echo "Pass Rate:      $PASS_RATE%"
echo "=========================================="
echo ""

# Export results if requested
if [ -n "$EXPORT_FILE" ]; then
    echo "[" > "$EXPORT_FILE"
    for i in ${!RESULTS[@]}; do
        echo "${RESULTS[$i]}" >> "$EXPORT_FILE"
        if [ $i -lt $((${#RESULTS[@]} - 1)) ]; then
            echo "," >> "$EXPORT_FILE"
        fi
    done
    echo "]" >> "$EXPORT_FILE"
    print_status "PASS" "Results exported to $EXPORT_FILE"
fi

# Exit with appropriate code
if [ $FAILED -eq 0 ] && [ $PASSED -eq $TOTAL ]; then
    print_status "PASS" "All tests passed!"
    exit 0
elif [ $FAILED -eq 0 ]; then
    print_status "PASS" "Tests completed with some partial results"
    exit 0
else
    print_status "FAIL" "Some tests failed"
    exit 1
fi
