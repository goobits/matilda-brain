# Matilda Brain CLI Command Checklist

## Basic Commands
- [x] `brain "prompt"` - Tested 2025-07-24
- [x] `brain ask "prompt"` - Tested 2025-07-24
- [x] `brain info <model>` - Tested 2025-07-24
- [x] `brain chat` - Tested 2025-07-24
- [x] `brain status` - Tested 2025-07-24
- [x] `brain models` - Tested 2025-07-24
- [x] `brain config` - Tested 2025-07-24
- [x] `brain --version` - Tested 2025-07-24

## Model Selection Options
- [x] `brain ask --model gpt-4 "prompt"` - Tested 2025-07-24
- [x] `brain ask -m @claude "prompt"` - Tested 2025-07-24
- [x] `brain ask --model openrouter/google/gemini-flash-1.5 "prompt"` - Tested 2025-07-24

## System Prompt Options
- [x] `brain ask --system "system prompt" "user prompt"` - Tested 2025-07-24
- [ ] `brain ask -s "system prompt" "user prompt"`

## Temperature Control
- [x] `brain ask --temperature 0.7 "prompt"` - Tested 2025-07-24
- [x] `brain ask -t 0.1 "prompt"` - Tested 2025-07-24

## Token Limits
- [x] `brain ask --max-tokens 100 "prompt"` - Tested 2025-07-24
- [ ] `brain ask --max-tokens 2000 "prompt"`

## Tools Options
- [x] `brain ask --tools "prompt"` - Tested 2025-07-24
- [ ] `brain ask --tools web "prompt"`
- [ ] `brain ask --tools code "prompt"`

## Output Modes
- [x] `brain ask --stream "prompt"` - Tested 2025-07-24
- [x] `brain ask --json "prompt"` - Tested 2025-07-24
- [ ] `brain ask --verbose "prompt"`
- [ ] `brain ask --debug "prompt"`
- [ ] `brain ask --code "prompt"`

## Chat Commands
- [x] `brain chat` - Tested 2025-07-24
- [x] `brain chat --model <model>` - Tested 2025-07-24
- [x] `brain chat --session <id>` - Tested 2025-07-24
- [x] `brain chat --tools` - Tested 2025-07-24
- [x] `brain chat --markdown` - Tested 2025-07-24
- [ ] `brain chat --list`
- [ ] `brain chat --resume`

## Config Commands
- [x] `brain config` - Tested 2025-07-24
- [x] `brain config list` - Tested 2025-07-24
- [x] `brain config get models.default` - Tested 2025-07-24
- [x] `brain config get models.aliases` - Tested 2025-07-24
- [ ] `brain config set models.default gpt-4`
- [ ] `brain config --reset`

## JSON Output Combinations
- [x] `brain ask --json "prompt"` - Tested 2025-07-24
- [x] `brain status --json` - Tested 2025-07-24
- [x] `brain models --json` - Tested 2025-07-24
- [x] `brain info <model> --json` - Tested 2025-07-24
- [x] `brain config list` - Tested 2025-07-24

## Pipeline Usage
- [x] `echo "text" | brain ask "transform this"` - Tested 2025-07-24
- [x] `echo "hello world" | brain ask "transform this"` - Tested 2025-07-24
- [ ] `cat file.txt | brain ask "summarize"`
- [ ] `echo '{"prompt": "hello"}' | brain ask`

## Model Aliases
- [x] `brain ask -m @claude "prompt"` - Tested 2025-07-24
- [x] `brain ask -m @gpt4 "prompt"` - Tested 2025-07-24
- [x] `brain ask -m @fast "prompt"` - Tested 2025-07-24
- [x] `brain ask -m @best "prompt"` - Tested 2025-07-24
- [x] `brain ask -m @coding "prompt"` - Tested 2025-07-24
- [x] `brain ask -m @local "prompt"` - Tested 2025-07-24
- [ ] `brain info @claude`

## Complex Combinations
- [x] `brain ask --model @claude --temperature 0.2 --tools --json "write a function"` - Tested 2025-07-24
- [x] `brain ask --json --model gpt-4 --max-tokens 500 "structured analysis"` - Tested 2025-07-24
- [x] `brain ask -m @gpt4 --stream --json "explain this algorithm"` - Tested 2025-07-24
- [x] `echo "data" | brain ask --model @claude --tools --json "analyze and research"` - Tested 2025-07-24
- [x] `brain ask --model @claude --temperature 0.7 --max-tokens 1000 --tools "research topic"` - Tested 2025-07-24
- [x] `brain ask -m @fast --json --stream "quick response in JSON format"` - Tested 2025-07-24
- [x] `cat input.txt | brain ask --model @coding --tools --json "analyze this code"` - Tested 2025-07-24
