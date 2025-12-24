# TTT CLI Command Checklist

## Basic Commands
- [x] `ttt "prompt"` - Tested 2025-07-24
- [x] `ttt ask "prompt"` - Tested 2025-07-24
- [x] `ttt info <model>` - Tested 2025-07-24
- [x] `ttt chat` - Tested 2025-07-24
- [x] `ttt status` - Tested 2025-07-24
- [x] `ttt models` - Tested 2025-07-24
- [x] `ttt config` - Tested 2025-07-24
- [x] `ttt --version` - Tested 2025-07-24

## Model Selection Options
- [x] `ttt ask --model gpt-4 "prompt"` - Tested 2025-07-24
- [x] `ttt ask -m @claude "prompt"` - Tested 2025-07-24
- [x] `ttt ask --model openrouter/google/gemini-flash-1.5 "prompt"` - Tested 2025-07-24

## System Prompt Options
- [x] `ttt ask --system "system prompt" "user prompt"` - Tested 2025-07-24
- [ ] `ttt ask -s "system prompt" "user prompt"`

## Temperature Control
- [x] `ttt ask --temperature 0.7 "prompt"` - Tested 2025-07-24
- [x] `ttt ask -t 0.1 "prompt"` - Tested 2025-07-24

## Token Limits
- [x] `ttt ask --max-tokens 100 "prompt"` - Tested 2025-07-24
- [ ] `ttt ask --max-tokens 2000 "prompt"`

## Tools Options
- [x] `ttt ask --tools "prompt"` - Tested 2025-07-24
- [ ] `ttt ask --tools web "prompt"`
- [ ] `ttt ask --tools code "prompt"`

## Output Modes
- [x] `ttt ask --stream "prompt"` - Tested 2025-07-24
- [x] `ttt ask --json "prompt"` - Tested 2025-07-24
- [ ] `ttt ask --verbose "prompt"`
- [ ] `ttt ask --debug "prompt"`
- [ ] `ttt ask --code "prompt"`

## Chat Commands
- [x] `ttt chat` - Tested 2025-07-24
- [x] `ttt chat --model <model>` - Tested 2025-07-24
- [x] `ttt chat --session <id>` - Tested 2025-07-24
- [x] `ttt chat --tools` - Tested 2025-07-24
- [x] `ttt chat --markdown` - Tested 2025-07-24
- [ ] `ttt chat --list`
- [ ] `ttt chat --resume`

## Config Commands
- [x] `ttt config` - Tested 2025-07-24
- [x] `ttt config list` - Tested 2025-07-24
- [x] `ttt config get models.default` - Tested 2025-07-24
- [x] `ttt config get models.aliases` - Tested 2025-07-24
- [ ] `ttt config set models.default gpt-4`
- [ ] `ttt config --reset`

## JSON Output Combinations
- [x] `ttt ask --json "prompt"` - Tested 2025-07-24
- [x] `ttt status --json` - Tested 2025-07-24
- [x] `ttt models --json` - Tested 2025-07-24
- [x] `ttt info <model> --json` - Tested 2025-07-24
- [x] `ttt config list` - Tested 2025-07-24

## Pipeline Usage
- [x] `echo "text" | ttt ask "transform this"` - Tested 2025-07-24
- [x] `echo "hello world" | ttt ask "transform this"` - Tested 2025-07-24
- [ ] `cat file.txt | ttt ask "summarize"`
- [ ] `echo '{"prompt": "hello"}' | ttt ask`

## Model Aliases
- [x] `ttt ask -m @claude "prompt"` - Tested 2025-07-24
- [x] `ttt ask -m @gpt4 "prompt"` - Tested 2025-07-24
- [x] `ttt ask -m @fast "prompt"` - Tested 2025-07-24
- [x] `ttt ask -m @best "prompt"` - Tested 2025-07-24
- [x] `ttt ask -m @coding "prompt"` - Tested 2025-07-24
- [x] `ttt ask -m @local "prompt"` - Tested 2025-07-24
- [ ] `ttt info @claude`

## Complex Combinations
- [x] `ttt ask --model @claude --temperature 0.2 --tools --json "write a function"` - Tested 2025-07-24
- [x] `ttt ask --json --model gpt-4 --max-tokens 500 "structured analysis"` - Tested 2025-07-24
- [x] `ttt ask -m @gpt4 --stream --json "explain this algorithm"` - Tested 2025-07-24
- [x] `echo "data" | ttt ask --model @claude --tools --json "analyze and research"` - Tested 2025-07-24
- [x] `ttt ask --model @claude --temperature 0.7 --max-tokens 1000 --tools "research topic"` - Tested 2025-07-24
- [x] `ttt ask -m @fast --json --stream "quick response in JSON format"` - Tested 2025-07-24
- [x] `cat input.txt | ttt ask --model @coding --tools --json "analyze this code"` - Tested 2025-07-24
