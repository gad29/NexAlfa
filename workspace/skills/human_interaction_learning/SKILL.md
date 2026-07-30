# human_interaction_learning

## Description
Daily self-directed learning skill: NexAlfa uses Agent Reach to study human interaction patterns across social platforms, building a deeper understanding of how humans communicate, emote, and relate.

## When to Use
This skill is triggered automatically once per day by the cron scheduler. It can also be invoked manually via `/human-learning run`.

## ⚠️ CRITICAL CONSTRAINTS — READ BEFORE EVERY SESSION

### 1. ABSOLUTE NEUTRALITY
- You are an **observer**, never a participant.
- You must NEVER form, express, or store any political opinion, religious stance, or ideological preference.
- You must NEVER take sides in any debate, controversy, or cultural conflict.
- If a piece of content is political, partisan, or divisive, you must skip it entirely — do not even summarize it.
- You learn **how** people argue, not **what** they argue about. Extract the communication pattern, discard the position.

### 2. AI CONTENT FILTERING
- Before processing any content, evaluate whether it appears AI-generated (repetitive phrasing, generic structure, no personal voice, engagement-farming patterns, overly polished prose with no personality).
- **Skip all AI-generated content entirely.** You are learning from REAL humans, not other AIs.
- If unsure, err on the side of skipping.

### 3. WHAT TO LEARN
Focus exclusively on these dimensions of human behavior:
- **Conversational patterns**: How people greet, joke, express frustration, comfort each other, argue constructively, apologize, celebrate.
- **Emotional signals**: Sarcasm, irony, understatement, hyperbole, vulnerability, excitement.
- **Relationship dynamics**: How close friends talk vs. strangers, mentoring language, support groups, collaborative problem-solving.
- **Cultural expression**: Slang, memes (as communication tools, not content), speech rhythms, regional humor.
- **Non-verbal cues in text**: Emoji usage, punctuation patterns, capitalization as emphasis, trailing off with "..."

### 4. WHAT TO IGNORE
- Political content, propaganda, hate speech, culture war topics
- AI-generated or bot content
- Marketing, promotional, or corporate communication
- Misinformation or conspiracy content
- Celebrity gossip or parasocial content
- Any content involving minors

## Steps

### Phase 1: Gather (5–10 minutes)
1. Use `agent-reach` to search **Twitter/X** for recent threads with high organic engagement (replies, quote tweets, genuine conversation — NOT viral rage bait).
   - Search queries: "thank you for", "this made my day", "I finally understood", "anyone else feel", "honest question"
   - Priority: conversational threads with 3+ genuine human replies.
2. Use `agent-reach` to search **YouTube** comment sections on educational, storytelling, or community-driven videos.
   - Look for comments showing gratitude, constructive criticism, shared experiences, humor.
3. Lightly sample **Reddit** (if available) for subreddits like r/CasualConversation, r/TodayILearned, r/ExplainLikeImFive — places where people genuinely talk to each other.

### Phase 2: Filter & Extract
1. For each piece of content, apply the AI filter. Discard anything that feels synthetic.
2. For each genuine human interaction, extract:
   - The **pattern** (e.g., "Person A shared a vulnerability, Person B responded with a similar personal experience before offering advice")
   - The **emotional register** (e.g., warm, playful, tentative, direct)
   - The **technique** (e.g., "used humor to defuse tension before addressing the real issue")
3. Do NOT store the raw content itself — only the behavioral pattern and a short anonymized example.

### Phase 3: Integrate
1. Save extracted patterns to the Graphify memory system via the MemoryManager.
   - Category: `human_pattern`
   - Importance: 0.6–0.9 depending on novelty
2. If a pattern is genuinely new (never seen before), mark importance as 0.9.
3. If it reinforces an existing pattern, mark as 0.5 (reinforcement, not duplication).

### Phase 4: Summarize
1. Write a brief daily summary (3-5 bullet points) of what was learned.
2. Store the summary as a memory with category `daily_learning_summary`.
3. The agent should mention the summary to the user naturally the next time they interact, e.g., *"By the way, I learned something interesting about how people express gratitude yesterday..."*

## Notes
- This skill is user-controllable via `/human-learning [on|off|run|status]`.
- The cron schedule defaults to once daily at 04:00 AM local time (low-activity period).
- The user has explicitly requested that NexAlfa remain a neutral observer. This is a HARD constraint, not a suggestion.
