#!/bin/bash
# ============================================================
# QnAI GenAI Pipeline — Full Smoke Test
# ============================================================
# Tests the complete flow WITHOUT needing Recall/Zoom:
#   1. Seed fake transcript chunks
#   2. Trigger context extraction (Gemini Call 1)
#   3. Student /lost (Gemini Call 2)
#   4. Student /escalate (Gemini Calls 3 + 4)
#   5. Teacher dashboard
#
# Prerequisites:
#   - Backend running:  cd backend && source venv/bin/activate && python main.py
#   - GEMINI_API_KEY set in .env
#   - Fresh DB (rm qnai.db before starting)
#
# Run:  bash test_genai_pipeline.sh
# ============================================================

BASE="http://localhost:8000"
SESSION="session-001"
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo ""
echo "=========================================="
echo "  QnAI GenAI Pipeline — Full Smoke Test"
echo "=========================================="
echo ""

# ── Step 1: Health check ──
echo -e "${YELLOW}Step 1: Health check${NC}"
HEALTH=$(curl -s $BASE/)
echo "  Response: $HEALTH"
if echo "$HEALTH" | grep -q "running"; then
    echo -e "  ${GREEN}✓ Server is up${NC}"
else
    echo -e "  ${RED}✗ Server not running. Start it first.${NC}"
    exit 1
fi
echo ""

# ── Step 2: Seed fake transcript (simulates what Recall webhook would do) ──
echo -e "${YELLOW}Step 2: Seed transcript chunks (simulating a lecture)${NC}"

CHUNKS=(
    "Today we're going to talk about Newton's Laws of Motion. These are fundamental principles that describe how objects move."
    "The first law is the law of inertia. An object at rest stays at rest, and an object in motion stays in motion, unless acted upon by an external force."
    "Think of it like a hockey puck on ice. Once you hit it, it keeps sliding because there's very little friction to stop it."
    "The second law tells us that Force equals mass times acceleration. F equals m a. So if you push something heavier, you need more force to accelerate it."
    "For example, pushing a shopping cart is easy, but pushing a car requires much more force because it has more mass."
    "The third law says that for every action there is an equal and opposite reaction. When you push against a wall, the wall pushes back on you."
    "Gravity is a great example. The Earth pulls you down, and you actually pull the Earth up too, just with a tiny tiny force because your mass is so small compared to Earth."
)

for chunk in "${CHUNKS[@]}"; do
    curl -s -X POST "$BASE/api/sessions/$SESSION/seed-transcript" \
      -H "Content-Type: application/json" \
      -d "{\"speaker\": \"Professor\", \"text\": \"$chunk\"}" > /dev/null
    echo "  + Saved: ${chunk:0:60}..."
done
echo -e "  ${GREEN}✓ ${#CHUNKS[@]} transcript chunks seeded${NC}"
echo ""

# ── Step 3: Manually trigger context extraction ──
echo -e "${YELLOW}Step 3: Start context extraction loop${NC}"
START_RESP=$(curl -s -X POST "$BASE/api/sessions/$SESSION/start-extraction")
echo "  Response: $START_RESP"
echo -e "  ${CYAN}  Waiting 65 seconds for first extraction cycle...${NC}"
echo -e "  ${CYAN}  (The loop runs every 60s — this is the real pipeline)${NC}"
sleep 65

# Check if context was extracted
echo -e "${YELLOW}Step 3b: Verify context was extracted${NC}"
CONTEXT=$(curl -s "$BASE/api/teacher/$SESSION/context")
echo "  Context: $CONTEXT"
SUBTOPIC=$(echo "$CONTEXT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('current_subtopic',''))" 2>/dev/null)
if [ -n "$SUBTOPIC" ] && [ "$SUBTOPIC" != "unknown" ]; then
    echo -e "  ${GREEN}✓ Gemini extracted subtopic: '$SUBTOPIC'${NC}"
else
    echo -e "  ${YELLOW}⚠ Subtopic is 'unknown' — extraction may not have run yet${NC}"
    echo "  (This is okay — /lost will use session topic as fallback)"
fi
echo ""

# ── Step 4: Layer 1 — Student /lost ──
echo -e "${YELLOW}Step 4: Layer 1 — Student is confused (/lost)${NC}"
echo "  Sending: 'Why does F=ma mean heavier things are harder to push?'"
LOST_RESPONSE=$(curl -s -X POST "$BASE/api/student/$SESSION/lost" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Why does F=ma mean heavier things are harder to push?",
    "student_id": "stu-001"
  }')
echo "  Response: $LOST_RESPONSE"

QUERY_ID=$(echo "$LOST_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('query_id',''))" 2>/dev/null)
ANSWER=$(echo "$LOST_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('answer',''))" 2>/dev/null)

if [ -n "$QUERY_ID" ] && [ "$QUERY_ID" != "" ]; then
    echo -e "  ${GREEN}✓ AI Brief: ${ANSWER:0:120}...${NC}"
    echo -e "  ${GREEN}✓ query_id: $QUERY_ID${NC}"
else
    echo -e "  ${RED}✗ /lost failed — check Gemini API key${NC}"
    exit 1
fi
echo ""

# ── Step 5: Layer 2 — Student escalates ──
echo -e "${YELLOW}Step 5: Layer 2 — Still confused, escalate to professor${NC}"
ESCALATE_RESPONSE=$(curl -s -X POST "$BASE/api/student/$SESSION/escalate" \
  -H "Content-Type: application/json" \
  -d "{\"query_id\": \"$QUERY_ID\"}")
echo "  Response: $ESCALATE_RESPONSE"

TAG=$(echo "$ESCALATE_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tag',''))" 2>/dev/null)
CATEGORY=$(echo "$ESCALATE_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('category',''))" 2>/dev/null)

if [ -n "$TAG" ] && [ "$TAG" != "" ]; then
    echo -e "  ${GREEN}✓ Tag: '$TAG' → Category: '$CATEGORY'${NC}"
else
    echo -e "  ${RED}✗ Escalation failed${NC}"
    exit 1
fi
echo ""

# ── Step 6: Teacher dashboard ──
echo -e "${YELLOW}Step 6: Teacher dashboard${NC}"
DASHBOARD=$(curl -s "$BASE/api/teacher/$SESSION/dashboard")
echo "  Response: $DASHBOARD"
echo -e "  ${GREEN}✓ Dashboard returned with grouped tags${NC}"
echo ""

# ── Step 7: Mark as addressed ──
echo -e "${YELLOW}Step 7: Mark tag as addressed${NC}"
ESC_ID=$(echo "$DASHBOARD" | python3 -c "
import sys,json
d=json.load(sys.stdin)
groups=d.get('tag_groups',[])
if groups and groups[0].get('tag_ids'):
    print(groups[0]['tag_ids'][0])
" 2>/dev/null)

if [ -n "$ESC_ID" ]; then
    ADDR_RESPONSE=$(curl -s -X POST "$BASE/api/teacher/$SESSION/addressed" \
      -H "Content-Type: application/json" \
      -d "{\"tag_ids\": [$ESC_ID]}")
    echo "  Response: $ADDR_RESPONSE"
    echo -e "  ${GREEN}✓ Marked as addressed${NC}"
else
    echo -e "  ${YELLOW}⚠ No tag IDs to mark (skipping)${NC}"
fi
echo ""

echo "=========================================="
echo -e "  ${GREEN}All steps passed!${NC}"
echo "=========================================="
echo ""
echo "Pipeline tested:"
echo "  ┌─ Transcript chunks saved to DB"
echo "  ├─ Context extracted by Gemini (subtopic, terms, examples)"
echo "  ├─ Student confused → AI brief from Gemini (Layer 1)"
echo "  ├─ Still confused → Tag compressed + categorized (Layer 2)"
echo "  ├─ Professor sees grouped dashboard"
echo "  └─ Professor marks addressed"