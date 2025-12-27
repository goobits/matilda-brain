#!/usr/bin/env python3
"""Auto-generated from goobits.yaml"""

import os
import sys
import importlib.util
from pathlib import Path
import rich_click as click
from rich_click import RichGroup

# Set up rich-click configuration globally
click.rich_click.USE_RICH_MARKUP = True
click.rich_click.USE_MARKDOWN = False  # Disable markdown to avoid conflicts
click.rich_click.MARKUP_MODE = "rich"

# Environment variables for additional control
os.environ["RICH_CLICK_USE_RICH_MARKUP"] = "1"
os.environ["RICH_CLICK_FORCE_TERMINAL"] = "1"
click.rich_click.SHOW_ARGUMENTS = True
click.rich_click.GROUP_ARGUMENTS_OPTIONS = True
click.rich_click.SHOW_METAVARS_COLUMN = False
click.rich_click.APPEND_METAVARS_HELP = True
click.rich_click.STYLE_ERRORS_SUGGESTION = "#ff5555"
click.rich_click.ERRORS_SUGGESTION = "Try running the '--help' flag for more information."
click.rich_click.ERRORS_EPILOGUE = "To find out more, visit https://github.com/anthropics/claude-code"
click.rich_click.MAX_WIDTH = 120  # Set reasonable width
click.rich_click.WIDTH = 120  # Set consistent width
click.rich_click.COLOR_SYSTEM = "auto"
click.rich_click.SHOW_SUBCOMMAND_ALIASES = True
click.rich_click.ALIGN_OPTIONS_SWITCHES = True
click.rich_click.STYLE_OPTION = "#ff79c6"  # Dracula Pink - for option flags
click.rich_click.STYLE_SWITCH = "#50fa7b"  # Dracula Green - for switches
click.rich_click.STYLE_METAVAR = "#8BE9FD not bold"  # Light cyan - for argument types (OPTIONS, COMMAND)
click.rich_click.STYLE_METAVAR_SEPARATOR = "#6272a4"  # Dracula Comment
click.rich_click.STYLE_HEADER_TEXT = "bold yellow"  # Bold yellow - for section headers
click.rich_click.STYLE_EPILOGUE_TEXT = "#6272a4"  # Dracula Comment
click.rich_click.STYLE_FOOTER_TEXT = "#6272a4"  # Dracula Comment
click.rich_click.STYLE_USAGE = "#BD93F9"  # Purple - for "Usage:" line
click.rich_click.STYLE_USAGE_COMMAND = "bold"  # Bold for main command name
click.rich_click.STYLE_DEPRECATED = "#ff5555"  # Dracula Red
click.rich_click.STYLE_HELPTEXT_FIRST_LINE = "#f8f8f2"  # Dracula Foreground
click.rich_click.STYLE_HELPTEXT = "#B3B8C0"  # Light gray - for help descriptions
click.rich_click.STYLE_OPTION_DEFAULT = "#ffb86c"  # Dracula Orange
click.rich_click.STYLE_REQUIRED_SHORT = "#ff5555"  # Dracula Red
click.rich_click.STYLE_REQUIRED_LONG = "#ff5555"  # Dracula Red
click.rich_click.STYLE_OPTIONS_PANEL_BORDER = "dim"  # Dim for subtle borders
click.rich_click.STYLE_COMMANDS_PANEL_BORDER = "dim"  # Dim for subtle borders
click.rich_click.STYLE_COMMAND = "#50fa7b"  # Dracula Green - for command names in list
click.rich_click.STYLE_COMMANDS_TABLE_COLUMN_WIDTH_RATIO = (1, 3)  # Command:Description ratio (1/4 : 3/4)


# Command groups will be set after main function is defined


# Hooks system - try to import app_hooks module
app_hooks = None

# Using configured hooks path: src/ttt/app_hooks.py
try:
    # First try as a module import (e.g., "matilda_brain.app_hooks")
    module_path = "src/ttt/app_hooks.py".replace(".py", "").replace("/", ".")
    if module_path.startswith("src."):
        module_path = module_path[4:]  # Remove 'src.' prefix

    try:
        app_hooks = importlib.import_module(module_path)
    except ImportError:
        # If module import fails, try relative import
        try:
            from . import app_hooks
        except ImportError:
            # If relative import fails, try file-based import as last resort
            script_dir = Path(__file__).parent.parent.parent
            hooks_file = script_dir / "src/ttt/app_hooks.py"

            if hooks_file.exists():
                spec = importlib.util.spec_from_file_location("app_hooks", hooks_file)
                if spec is not None and spec.loader is not None:
                    app_hooks = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(app_hooks)
except (ImportError, AttributeError, OSError, FileNotFoundError):
    # No hooks module found, use default behavior
    pass


# Built-in commands


def builtin_upgrade_command(check_only=False, pre=False, version=None, dry_run=False):
    """Built-in upgrade function for TTT - Text to Text - uses enhanced setup.sh script."""
    import subprocess
    import sys
    from pathlib import Path

    if check_only:
        print("Checking for updates to TTT - Text to Text...")
        print("Update check not yet implemented. Run without --check to upgrade.")
        return

    if dry_run:
        print("Dry run - would execute: pipx upgrade goobits-ttt")
        return

    # Find the setup.sh script - look in common locations
    setup_script = None
    search_paths = [
        Path(__file__).parent / "setup.sh",  # Package directory (installed packages)
        Path(__file__).parent.parent / "setup.sh",  # Development mode
        Path.home() / ".local" / "share" / "goobits-ttt" / "setup.sh",  # User data
        # Remove Path.cwd() to prevent cross-contamination
    ]

    for path in search_paths:
        if path.exists():
            setup_script = path
            break

    if setup_script is None:
        # Fallback to basic upgrade if setup.sh not found
        print("Enhanced setup script not found. Using basic upgrade for TTT - Text to Text...")
        import shutil

        package_name = "goobits-ttt"
        pypi_name = "goobits-ttt"

        if shutil.which("pipx"):
            result = subprocess.run(["pipx", "list"], capture_output=True, text=True)
            if package_name in result.stdout or pypi_name in result.stdout:
                cmd = ["pipx", "upgrade", pypi_name]
            else:
                cmd = [sys.executable, "-m", "pip", "install", "--upgrade", pypi_name]
        else:
            cmd = [sys.executable, "-m", "pip", "install", "--upgrade", pypi_name]

        result = subprocess.run(cmd)
        if result.returncode == 0:
            print("✅ TTT - Text to Text upgraded successfully!")
            print("Run 'ttt --version' to verify the new version.")
        else:
            print(f"❌ Upgrade failed with exit code {result.returncode}")
            sys.exit(1)
        return

    # Use the enhanced setup.sh script
    result = subprocess.run([str(setup_script), "upgrade"])
    sys.exit(result.returncode)


def load_plugins(cli_group):
    """Load plugins from the conventional plugin directory."""
    # Define plugin directories to search
    plugin_dirs = [
        # User-specific plugin directory
        Path.home() / ".config" / "goobits" / "GOOBITS TTT CLI" / "plugins",
        # Local plugin directory (same as script)
        Path(__file__).parent / "plugins",
    ]

    for plugin_dir in plugin_dirs:
        if not plugin_dir.exists():
            continue

        # Add plugin directory to Python path
        sys.path.insert(0, str(plugin_dir))

        # Scan for plugin files
        for plugin_file in plugin_dir.glob("*.py"):
            if plugin_file.name.startswith("_"):
                continue

            # Skip core system files that aren't plugins
            if plugin_file.name in ["loader.py", "__init__.py"]:
                continue

            plugin_name = plugin_file.stem

            try:
                # Import the plugin module
                spec = importlib.util.spec_from_file_location(plugin_name, plugin_file)
                plugin_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(plugin_module)

                # Call register_plugin if it exists
                if hasattr(plugin_module, "register_plugin"):
                    plugin_module.register_plugin(cli_group)
                    click.echo(f"Loaded plugin: {plugin_name}", err=True)
            except Exception as e:
                click.echo(f"Failed to load plugin {plugin_name}: {e}", err=True)


def get_version():
    """Get version from pyproject.toml or __init__.py"""
    import re

    try:
        # Try to get version from pyproject.toml FIRST (most authoritative)
        # Look in multiple possible locations
        possible_paths = [
            Path(__file__).parent.parent / "pyproject.toml",  # For flat structure
            Path(__file__).parent.parent.parent / "pyproject.toml",  # For src/ structure
        ]
        toml_path = None
        for path in possible_paths:
            if path.exists():
                toml_path = path
                break
        if toml_path:
            content = toml_path.read_text()
            match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', content)
            if match:
                return match.group(1)
    except (FileNotFoundError, PermissionError, OSError, AttributeError):
        pass

    try:
        # Fallback to __init__.py
        init_path = Path(__file__).parent / "__init__.py"
        if init_path.exists():
            content = init_path.read_text()
            match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
            if match:
                return match.group(1)
    except (FileNotFoundError, PermissionError, OSError, AttributeError):
        pass

    # Final fallback
    return "1.0.0"


def show_help_json(ctx, param, value):
    """Callback for --help-json option."""
    if not value or ctx.resilient_parsing:
        return
    # The triple quotes are important to correctly handle the multi-line JSON string
    click.echo("""{
  "name": "GOOBITS TTT CLI",
  "version": null,
  "display_version": true,
  "tagline": "Talk to Transformer",
  "description": "AI-powered conversations, straight from your command line",
  "icon": "🤖",
  "header_sections": [
    {
      "title": "💡 Quick Start",
      "icon": null,
      "items": [
        {
          "item": "ttt \\"What is the meaning of life?\\"",
          "desc": "Instant response",
          "style": "example"
        },
        {
          "item": "ttt chat",
          "desc": "Interactive session",
          "style": "example"
        },
        {
          "item": "ttt models",
          "desc": "Explore available models",
          "style": "example"
        },
        {
          "item": "ttt config set model gpt-4",
          "desc": "Set your preferred model",
          "style": "example"
        }
      ]
    },
    {
      "title": "🔑 Initial Setup",
      "icon": null,
      "items": [
        {
          "item": "1. See providers",
          "desc": "ttt providers",
          "style": "setup"
        },
        {
          "item": "2. Add API key",
          "desc": "export OPENROUTER_API_KEY='your-key-here'",
          "style": "setup"
        },
        {
          "item": "3. Check setup",
          "desc": "ttt status",
          "style": "setup"
        },
        {
          "item": "4. Start chatting",
          "desc": "ttt chat",
          "style": "setup"
        }
      ]
    }
  ],
  "footer_note": "📚 For detailed help on a command, run: [color(2)]ttt [COMMAND][/color(2)] [#ff79c6]--help[/#ff79c6]",
  "options": [],
  "commands": {
    "ask": {
      "desc": "Quickly ask one-off questions",
      "icon": "💬",
      "is_default": true,
      "lifecycle": "standard",
      "args": [
        {
          "name": "prompt",
          "desc": "The question or prompt",
          "nargs": "*",
          "choices": null,
          "required": true
        }
      ],
      "options": [
        {
          "name": "model",
          "short": "m",
          "type": "str",
          "desc": "LLM model to use",
          "default": null,
          "choices": null,
          "multiple": false
        },
        {
          "name": "temperature",
          "short": "t",
          "type": "float",
          "desc": "Sampling temperature (0.0-2.0)",
          "default": 0.7,
          "choices": null,
          "multiple": false
        },
        {
          "name": "max-tokens",
          "short": null,
          "type": "int",
          "desc": "Maximum response length",
          "default": null,
          "choices": null,
          "multiple": false
        },
        {
          "name": "tools",
          "short": null,
          "type": "bool",
          "desc": "Enable tool usage",
          "default": false,
          "choices": null,
          "multiple": false
        },
        {
          "name": "session",
          "short": "s",
          "type": "str",
          "desc": "Session ID for context",
          "default": null,
          "choices": null,
          "multiple": false
        },
        {
          "name": "system",
          "short": null,
          "type": "str",
          "desc": "System prompt to set AI behavior",
          "default": null,
          "choices": null,
          "multiple": false
        },
        {
          "name": "stream",
          "short": null,
          "type": "bool",
          "desc": "Stream the response",
          "default": true,
          "choices": null,
          "multiple": false
        },
        {
          "name": "json",
          "short": null,
          "type": "flag",
          "desc": "Output response in JSON format",
          "default": null,
          "choices": null,
          "multiple": false
        }
      ],
      "subcommands": null
    },
    "chat": {
      "desc": "Chat interactively with AI",
      "icon": "💬",
      "is_default": false,
      "lifecycle": "standard",
      "args": [],
      "options": [
        {
          "name": "model",
          "short": "m",
          "type": "str",
          "desc": "LLM model to use",
          "default": null,
          "choices": null,
          "multiple": false
        },
        {
          "name": "session",
          "short": "s",
          "type": "str",
          "desc": "Session ID to resume or create",
          "default": null,
          "choices": null,
          "multiple": false
        },
        {
          "name": "tools",
          "short": null,
          "type": "bool",
          "desc": "Enable tool usage in chat",
          "default": false,
          "choices": null,
          "multiple": false
        },
        {
          "name": "markdown",
          "short": null,
          "type": "bool",
          "desc": "Render markdown in responses",
          "default": true,
          "choices": null,
          "multiple": false
        }
      ],
      "subcommands": null
    },
    "list": {
      "desc": "See available resources",
      "icon": "📜",
      "is_default": false,
      "lifecycle": "standard",
      "args": [
        {
          "name": "resource",
          "desc": "Type of resource to list",
          "nargs": null,
          "choices": [
            "models",
            "sessions",
            "tools"
          ],
          "required": false
        }
      ],
      "options": [
        {
          "name": "format",
          "short": "f",
          "type": "str",
          "desc": "Output format",
          "default": "table",
          "choices": [
            "table",
            "json",
            "yaml"
          ],
          "multiple": false
        },
        {
          "name": "verbose",
          "short": "v",
          "type": "bool",
          "desc": "Show detailed information",
          "default": false,
          "choices": null,
          "multiple": false
        }
      ],
      "subcommands": null
    },
    "status": {
      "desc": "Verify system and API health",
      "icon": "✅",
      "is_default": false,
      "lifecycle": "standard",
      "args": [],
      "options": [
        {
          "name": "json",
          "short": null,
          "type": "flag",
          "desc": "Output status in JSON format",
          "default": null,
          "choices": null,
          "multiple": false
        }
      ],
      "subcommands": null
    },
    "models": {
      "desc": "View AI models",
      "icon": "🧠",
      "is_default": false,
      "lifecycle": "standard",
      "args": [],
      "options": [
        {
          "name": "json",
          "short": null,
          "type": "flag",
          "desc": "Output models in JSON format",
          "default": null,
          "choices": null,
          "multiple": false
        }
      ],
      "subcommands": null
    },
    "info": {
      "desc": "Detailed model information",
      "icon": "ℹ️",
      "is_default": false,
      "lifecycle": "standard",
      "args": [
        {
          "name": "model",
          "desc": "Model name",
          "nargs": null,
          "choices": null,
          "required": false
        }
      ],
      "options": [
        {
          "name": "json",
          "short": null,
          "type": "flag",
          "desc": "Output model info in JSON format",
          "default": null,
          "choices": null,
          "multiple": false
        }
      ],
      "subcommands": null
    },
    "export": {
      "desc": "Save your chat history",
      "icon": "💾",
      "is_default": false,
      "lifecycle": "standard",
      "args": [
        {
          "name": "session",
          "desc": "Session ID to export",
          "nargs": null,
          "choices": null,
          "required": false
        }
      ],
      "options": [
        {
          "name": "format",
          "short": "f",
          "type": "str",
          "desc": "Export format",
          "default": "markdown",
          "choices": [
            "markdown",
            "json",
            "txt"
          ],
          "multiple": false
        },
        {
          "name": "output",
          "short": "o",
          "type": "str",
          "desc": "Output file path",
          "default": null,
          "choices": null,
          "multiple": false
        },
        {
          "name": "include-metadata",
          "short": null,
          "type": "bool",
          "desc": "Include timestamps and model info",
          "default": false,
          "choices": null,
          "multiple": false
        }
      ],
      "subcommands": null
    },
    "config": {
      "desc": "Customize your setup",
      "icon": "⚙️",
      "is_default": false,
      "lifecycle": "standard",
      "args": [],
      "options": [],
      "subcommands": {
        "get": {
          "desc": "Get a configuration value",
          "icon": null,
          "is_default": false,
          "lifecycle": "standard",
          "args": [
            {
              "name": "key",
              "desc": "Configuration key",
              "nargs": null,
              "choices": null,
              "required": true
            }
          ],
          "options": [],
          "subcommands": null
        },
        "set": {
          "desc": "Set a configuration value",
          "icon": null,
          "is_default": false,
          "lifecycle": "standard",
          "args": [
            {
              "name": "key",
              "desc": "Configuration key",
              "nargs": null,
              "choices": null,
              "required": true
            },
            {
              "name": "value",
              "desc": "Configuration value",
              "nargs": null,
              "choices": null,
              "required": true
            }
          ],
          "options": [],
          "subcommands": null
        },
        "list": {
          "desc": "List all configuration",
          "icon": null,
          "is_default": false,
          "lifecycle": "standard",
          "args": [],
          "options": [
            {
              "name": "show-secrets",
              "short": null,
              "type": "bool",
              "desc": "Include API keys in output",
              "default": false,
              "choices": null,
              "multiple": false
            }
          ],
          "subcommands": null
        }
      }
    },
    "tools": {
      "desc": "Manage CLI tools and extensions",
      "icon": "🛠️",
      "is_default": false,
      "lifecycle": "standard",
      "args": [],
      "options": [],
      "subcommands": {
        "enable": {
          "desc": "Enable a tool",
          "icon": null,
          "is_default": false,
          "lifecycle": "standard",
          "args": [
            {
              "name": "tool_name",
              "desc": "Name of the tool to enable",
              "nargs": null,
              "choices": null,
              "required": true
            }
          ],
          "options": [],
          "subcommands": null
        },
        "disable": {
          "desc": "Disable a tool",
          "icon": null,
          "is_default": false,
          "lifecycle": "standard",
          "args": [
            {
              "name": "tool_name",
              "desc": "Name of the tool to disable",
              "nargs": null,
              "choices": null,
              "required": true
            }
          ],
          "options": [],
          "subcommands": null
        },
        "list": {
          "desc": "List all tools",
          "icon": null,
          "is_default": false,
          "lifecycle": "standard",
          "args": [],
          "options": [
            {
              "name": "show-disabled",
              "short": null,
              "type": "bool",
              "desc": "Include disabled tools",
              "default": false,
              "choices": null,
              "multiple": false
            }
          ],
          "subcommands": null
        }
      }
    }
  },
  "command_groups": [
    {
      "name": "Core Commands",
      "commands": [
        "ask",
        "chat",
        "list",
        "status"
      ],
      "icon": null
    },
    {
      "name": "Model Management",
      "commands": [
        "models",
        "info"
      ],
      "icon": null
    },
    {
      "name": "Configuration",
      "commands": [
        "config",
        "tools"
      ],
      "icon": null
    },
    {
      "name": "Data Management",
      "commands": [
        "export"
      ],
      "icon": null
    }
  ],
  "config": {
    "rich_help_panel": true,
    "show_metavars_column": false,
    "append_metavars_help": true,
    "style_errors_suggestion": true,
    "max_width": 120
  },
  "enable_recursive_help": true,
  "enable_help_json": true
}""")
    ctx.exit()


class DefaultGroup(RichGroup):
    """Allow a default command to be invoked without being specified."""

    def __init__(self, *args, default=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.default_command = default

    def main(self, *args, **kwargs):
        """Override main to handle stdin input when no command is provided."""
        import sys
        import os
        import stat

        # Check if we need to inject the default command due to stdin input
        if len(sys.argv) == 1 and self.default_command:  # Only script name provided
            # Check if stdin is coming from a pipe or redirection
            has_stdin = False
            try:
                # Check if stdin is a pipe or file (not a terminal)
                stdin_stat = os.fstat(sys.stdin.fileno())
                has_stdin = stat.S_ISFIFO(stdin_stat.st_mode) or stat.S_ISREG(stdin_stat.st_mode)
            except (OSError, AttributeError, ValueError):
                # Fallback to isatty check
                has_stdin = not sys.stdin.isatty()

            if has_stdin:
                # Inject the default command into sys.argv
                sys.argv.append(self.default_command)

        return super().main(*args, **kwargs)

    def resolve_command(self, ctx, args):
        import sys
        import os

        try:
            # Try normal command resolution first
            return super().resolve_command(ctx, args)
        except click.UsageError:
            # If no command found and we have a default, use it
            # Check if stdin is coming from a pipe or redirection
            has_stdin = False
            try:
                # Check if stdin is a pipe or file (not a terminal)
                stdin_stat = os.fstat(sys.stdin.fileno())
                # Use S_ISFIFO to check if it's a pipe, or S_ISREG to check if it's a regular file
                import stat

                has_stdin = stat.S_ISFIFO(stdin_stat.st_mode) or stat.S_ISREG(stdin_stat.st_mode)
            except (OSError, AttributeError, ValueError):
                # Fallback to isatty check
                has_stdin = not sys.stdin.isatty()

            is_help_request = any(arg in ["--help-all", "--help-json"] for arg in args)

            if self.default_command and not is_help_request:
                # Trigger default command if:
                # 1. We have args (existing behavior)
                # 2. We have stdin input (new behavior for pipes)
                if args or has_stdin:
                    cmd = self.commands.get(self.default_command)
                    if cmd:
                        # Return command name, command object, and all args
                        return self.default_command, cmd, args
            raise


@click.group(
    cls=DefaultGroup, default="ask", context_settings={"help_option_names": ["-h", "--help"], "max_content_width": 120}
)
@click.version_option(version=get_version(), prog_name="GOOBITS TTT CLI")
@click.pass_context
@click.option(
    "--help-json",
    is_flag=True,
    callback=show_help_json,
    is_eager=True,
    help="Output CLI structure as JSON.",
    hidden=True,
)
@click.option("--help-all", is_flag=True, is_eager=True, help="Show help for all commands.", hidden=True)
@click.option("--debug", is_flag=True, help="Show full error traces and debug information")
def main(ctx, help_json=False, help_all=False, debug=False):
    """🤖 [bold color(6)]GOOBITS TTT CLI v1.0.3[/bold color(6)] - Talk to Transformer


    \b
    [#B3B8C0]AI-powered conversations, straight from your command line[/#B3B8C0]




    [bold yellow]💡 Quick Start[/bold yellow]


    [green]   ttt "What is the meaning of life?"  [/green] [italic][#B3B8C0]# Instant response[/#B3B8C0][/italic]


    [green]   ttt chat                            [/green] [italic][#B3B8C0]# Interactive session[/#B3B8C0][/italic]


    [green]   ttt models                          [/green] [italic][#B3B8C0]# Explore available models[/#B3B8C0][/italic]


    [green]   ttt config set model gpt-4          [/green] [italic][#B3B8C0]# Set your preferred model[/#B3B8C0][/italic]

    [green] [/green]

    [bold yellow]🔑 Initial Setup[/bold yellow]


    [#B3B8C0]   1. See providers:  [/#B3B8C0][green]ttt providers[/green]

    [#B3B8C0]   2. Add API key:    [/#B3B8C0][green]export OPENROUTER_API_KEY='your-key-here'[/green]

    [#B3B8C0]   3. Check setup:    [/#B3B8C0][green]ttt status[/green]

    [#B3B8C0]   4. Start chatting: [/#B3B8C0][green]ttt chat[/green]
    [green] [/green]



    [#B3B8C0]📚 For detailed help on a command, run: [color(2)]ttt [COMMAND][/color(2)] [#ff79c6]--help[/#ff79c6][/#B3B8C0]

    """

    if help_all:
        # Print main help
        click.echo(ctx.get_help())
        click.echo()  # Add a blank line for spacing

        # Get a list of all command names
        commands_to_show = sorted(ctx.command.list_commands(ctx))

        for cmd_name in commands_to_show:
            command = ctx.command.get_command(ctx, cmd_name)

            # Create a new context for the subcommand
            sub_ctx = click.Context(command, info_name=cmd_name, parent=ctx)

            # Print a separator and the subcommand's help
            click.echo("=" * 20 + f" HELP FOR: {cmd_name} " + "=" * 20)
            click.echo(sub_ctx.get_help())
            click.echo()  # Add a blank line for spacing

        # Exit after printing all help
        ctx.exit()

    # Store global options in context for use by commands
    ctx.ensure_object(dict)
    ctx.obj["debug"] = debug

    pass


# Replace the version placeholder with dynamic version in the main command docstring


# Set command groups after main function is defined
click.rich_click.COMMAND_GROUPS = {
    "main": [
        {
            "name": "Core Commands",
            "commands": ["ask", "chat", "list", "status"],
        },
        {
            "name": "Model Management",
            "commands": ["models", "info"],
        },
        {
            "name": "Configuration",
            "commands": ["config", "tools"],
        },
        {
            "name": "Data Management",
            "commands": ["export"],
        },
    ]
}


# Built-in upgrade command (enabled by default)


@main.command()
@click.option("--check", is_flag=True, help="Check for updates without installing")
@click.option("--version", type=str, help="Install specific version")
@click.option("--pre", is_flag=True, help="Include pre-release versions")
@click.option("--dry-run", is_flag=True, help="Show what would be done without doing it")
def upgrade(check, version, pre, dry_run):
    """Upgrade TTT - Text to Text to the latest version."""
    builtin_upgrade_command(check_only=check, version=version, pre=pre, dry_run=dry_run)


@main.command()
@click.pass_context
@click.argument("PROMPT", nargs=-1)
@click.option("-m", "--model", type=str, help="LLM model to use")
@click.option("-t", "--temperature", type=float, default=0.7, help="Sampling temperature (0.0-2.0)")
@click.option("--max-tokens", type=int, help="Maximum response length")
@click.option("--tools", type=bool, default=False, help="Enable tool usage")
@click.option("-s", "--session", type=str, help="Session ID for context")
@click.option("--system", type=str, help="System prompt to set AI behavior")
@click.option("--stream", type=bool, default=True, help="Stream the response")
@click.option("--json", is_flag=True, help="Output response in JSON format")
def ask(ctx, prompt, model, temperature, max_tokens, tools, session, system, stream, json):
    """💬 Quickly ask one-off questions"""

    # Check for built-in commands first

    # Standard command - use the existing hook pattern
    hook_name = "on_ask"
    if app_hooks and hasattr(app_hooks, hook_name):
        # Call the hook with all parameters
        hook_func = getattr(app_hooks, hook_name)

        # Prepare arguments including global options
        kwargs = {}
        kwargs["command_name"] = "ask"  # Pass command name for all commands

        kwargs["prompt"] = prompt

        kwargs["model"] = model

        kwargs["temperature"] = temperature

        kwargs["max_tokens"] = max_tokens

        kwargs["tools"] = tools

        kwargs["session"] = session

        kwargs["system"] = system

        kwargs["stream"] = stream

        kwargs["json"] = json

        # Add global options from context
        if ctx and ctx.obj:
            kwargs["debug"] = ctx.obj.get("debug", False)

        result = hook_func(**kwargs)
        return result
    else:
        # Default placeholder behavior
        click.echo("Executing ask command...")

        click.echo(f"  prompt: {prompt}")

        click.echo(f"  model: {model}")

        click.echo(f"  temperature: {temperature}")

        click.echo(f"  max-tokens: {max_tokens}")

        click.echo(f"  tools: {tools}")

        click.echo(f"  session: {session}")

        click.echo(f"  system: {system}")

        click.echo(f"  stream: {stream}")

        click.echo(f"  json: {json}")


@main.command()
@click.pass_context
@click.option("-m", "--model", type=str, help="LLM model to use")
@click.option("-s", "--session", type=str, help="Session ID to resume or create")
@click.option("--tools", type=bool, default=False, help="Enable tool usage in chat")
def chat(ctx, model, session, tools):
    """💬 Chat interactively with AI"""

    # Check for built-in commands first

    # Standard command - use the existing hook pattern
    hook_name = "on_chat"
    if app_hooks and hasattr(app_hooks, hook_name):
        # Call the hook with all parameters
        hook_func = getattr(app_hooks, hook_name)

        # Prepare arguments including global options
        kwargs = {}
        kwargs["command_name"] = "chat"  # Pass command name for all commands

        kwargs["model"] = model

        kwargs["session"] = session

        kwargs["tools"] = tools

        kwargs["markdown"] = markdown

        # Add global options from context
        if ctx and ctx.obj:
            kwargs["debug"] = ctx.obj.get("debug", False)

        result = hook_func(**kwargs)
        return result
    else:
        # Default placeholder behavior
        click.echo("Executing chat command...")

        click.echo(f"  model: {model}")

        click.echo(f"  session: {session}")

        click.echo(f"  tools: {tools}")

        click.echo(f"  markdown: {markdown}")


@main.command()
@click.pass_context
@click.argument("MESSAGE", nargs=-1)
@click.option("--system", type=str, default=None, help="System prompt to set context")
@click.option("--history", type=str, default=None, help="Path to JSON file with conversation history")
@click.option("--tools", type=str, default=None, help="Comma-separated tool names to enable")
@click.option("-m", "--model", type=str, default=None, help="LLM model to use")
@click.option("-t", "--temperature", type=float, default=0.7, help="Sampling temperature (0.0-2.0)")
@click.option("--max-tokens", type=int, default=2048, help="Maximum response length")
def stateless(ctx, message, system, history, tools, model, temperature, max_tokens):
    """⚡ Execute stateless AI request without session"""

    # Check for built-in commands first

    # Standard command - use the existing hook pattern
    hook_name = "on_stateless"
    if app_hooks and hasattr(app_hooks, hook_name):
        # Call the hook with all parameters
        hook_func = getattr(app_hooks, hook_name)

        # Prepare arguments including global options
        kwargs = {}
        kwargs["command_name"] = "stateless"  # Pass command name for all commands

        kwargs["message"] = message

        kwargs["system"] = system

        kwargs["history"] = history

        kwargs["tools"] = tools

        kwargs["model"] = model

        kwargs["temperature"] = temperature

        kwargs["max_tokens"] = max_tokens

        # Add global options from context
        if ctx and ctx.obj:
            kwargs["debug"] = ctx.obj.get("debug", False)

        result = hook_func(**kwargs)
        return result
    else:
        # Default placeholder behavior
        click.echo("Executing stateless command...")

        click.echo(f"  message: {message}")

        click.echo(f"  system: {system}")

        click.echo(f"  history: {history}")

        click.echo(f"  tools: {tools}")

        click.echo(f"  model: {model}")

        click.echo(f"  temperature: {temperature}")

        click.echo(f"  max_tokens: {max_tokens}")


@main.command()
@click.pass_context
@click.argument("RESOURCE", required=False, default=None, type=click.Choice(["models", "sessions", "tools"]))
@click.option("-f", "--format", type=click.Choice(["table", "json", "yaml"]), default="table", help="Output format")
def list(ctx, resource, format):
    """📜 See available resources"""

    # Check for built-in commands first

    # Standard command - use the existing hook pattern
    hook_name = "on_list"
    if app_hooks and hasattr(app_hooks, hook_name):
        # Call the hook with all parameters
        hook_func = getattr(app_hooks, hook_name)

        # Prepare arguments including global options
        kwargs = {}
        kwargs["command_name"] = "list"  # Pass command name for all commands

        kwargs["resource"] = resource

        kwargs["format"] = format

        kwargs["verbose"] = verbose

        # Add global options from context
        if ctx and ctx.obj:
            kwargs["debug"] = ctx.obj.get("debug", False)

        result = hook_func(**kwargs)
        return result
    else:
        # Default placeholder behavior
        click.echo("Executing list command...")

        click.echo(f"  resource: {resource}")

        click.echo(f"  format: {format}")

        click.echo(f"  verbose: {verbose}")


@main.command()
@click.pass_context
@click.option("--json", is_flag=True, help="Output status in JSON format")
def status(ctx, json):
    """✅ Verify system and API health"""

    # Check for built-in commands first

    # Standard command - use the existing hook pattern
    hook_name = "on_status"
    if app_hooks and hasattr(app_hooks, hook_name):
        # Call the hook with all parameters
        hook_func = getattr(app_hooks, hook_name)

        # Prepare arguments including global options
        kwargs = {}
        kwargs["command_name"] = "status"  # Pass command name for all commands

        kwargs["json"] = json

        # Add global options from context
        if ctx and ctx.obj:
            kwargs["debug"] = ctx.obj.get("debug", False)

        result = hook_func(**kwargs)
        return result
    else:
        # Default placeholder behavior
        click.echo("Executing status command...")

        click.echo(f"  json: {json}")


@main.command()
@click.pass_context
@click.option("--json", is_flag=True, help="Output models in JSON format")
def models(ctx, json):
    """🧠 View AI models"""

    # Check for built-in commands first

    # Standard command - use the existing hook pattern
    hook_name = "on_models"
    if app_hooks and hasattr(app_hooks, hook_name):
        # Call the hook with all parameters
        hook_func = getattr(app_hooks, hook_name)

        # Prepare arguments including global options
        kwargs = {}
        kwargs["command_name"] = "models"  # Pass command name for all commands

        kwargs["json"] = json

        # Add global options from context
        if ctx and ctx.obj:
            kwargs["debug"] = ctx.obj.get("debug", False)

        result = hook_func(**kwargs)
        return result
    else:
        # Default placeholder behavior
        click.echo("Executing models command...")

        click.echo(f"  json: {json}")


@main.command()
@click.pass_context
@click.argument("MODEL", required=False, default=None)
@click.option("--json", is_flag=True, help="Output model info in JSON format")
def info(ctx, model, json):
    """ℹ️  Detailed model information"""

    # Check for built-in commands first

    # Standard command - use the existing hook pattern
    hook_name = "on_info"
    if app_hooks and hasattr(app_hooks, hook_name):
        # Call the hook with all parameters
        hook_func = getattr(app_hooks, hook_name)

        # Prepare arguments including global options
        kwargs = {}
        kwargs["command_name"] = "info"  # Pass command name for all commands

        kwargs["model"] = model

        kwargs["json"] = json

        # Add global options from context
        if ctx and ctx.obj:
            kwargs["debug"] = ctx.obj.get("debug", False)

        result = hook_func(**kwargs)
        return result
    else:
        # Default placeholder behavior
        click.echo("Executing info command...")

        click.echo(f"  model: {model}")

        click.echo(f"  json: {json}")


@main.command()
@click.pass_context
@click.argument("SESSION", required=False, default=None)
@click.option(
    "-f", "--format", type=click.Choice(["markdown", "json", "txt"]), default="markdown", help="Export format"
)
@click.option("-o", "--output", type=str, help="Output file path")
@click.option("--include-metadata", type=bool, default=False, help="Include timestamps and model info")
def export(ctx, session, format, output, include_metadata):
    """💾 Save your chat history"""

    # Check for built-in commands first

    # Standard command - use the existing hook pattern
    hook_name = "on_export"
    if app_hooks and hasattr(app_hooks, hook_name):
        # Call the hook with all parameters
        hook_func = getattr(app_hooks, hook_name)

        # Prepare arguments including global options
        kwargs = {}
        kwargs["command_name"] = "export"  # Pass command name for all commands

        kwargs["session"] = session

        kwargs["format"] = format

        kwargs["output"] = output

        kwargs["include_metadata"] = include_metadata

        # Add global options from context
        if ctx and ctx.obj:
            kwargs["debug"] = ctx.obj.get("debug", False)

        result = hook_func(**kwargs)
        return result
    else:
        # Default placeholder behavior
        click.echo("Executing export command...")

        click.echo(f"  session: {session}")

        click.echo(f"  format: {format}")

        click.echo(f"  output: {output}")

        click.echo(f"  include-metadata: {include_metadata}")


@main.group()
def config():
    """⚙️  Customize your setup"""
    pass


@config.command()
@click.pass_context
@click.argument("KEY")
def get(ctx, key):
    """Get a configuration value"""
    # Check if hook function exists
    hook_name = "on_config_get"
    if app_hooks and hasattr(app_hooks, hook_name):
        # Call the hook with all parameters
        hook_func = getattr(app_hooks, hook_name)

        # Prepare arguments including global options
        kwargs = {}
        kwargs["command_name"] = "get"  # Pass command name for all commands

        kwargs["key"] = key

        # Add global options from context
        if ctx and ctx.obj:
            kwargs["debug"] = ctx.obj.get("debug", False)

        result = hook_func(**kwargs)
        return result
    else:
        # Default placeholder behavior
        click.echo("Executing get command...")

        click.echo(f"  key: {key}")


@config.command()
@click.pass_context
@click.argument("KEY")
@click.argument("VALUE")
def set(ctx, key, value):
    """Set a configuration value"""
    # Check if hook function exists
    hook_name = "on_config_set"
    if app_hooks and hasattr(app_hooks, hook_name):
        # Call the hook with all parameters
        hook_func = getattr(app_hooks, hook_name)

        # Prepare arguments including global options
        kwargs = {}
        kwargs["command_name"] = "set"  # Pass command name for all commands

        kwargs["key"] = key

        kwargs["value"] = value

        # Add global options from context
        if ctx and ctx.obj:
            kwargs["debug"] = ctx.obj.get("debug", False)

        result = hook_func(**kwargs)
        return result
    else:
        # Default placeholder behavior
        click.echo("Executing set command...")

        click.echo(f"  key: {key}")

        click.echo(f"  value: {value}")


@config.command(name="list")
@click.pass_context
@click.option("--show-secrets", type=bool, default=False, help="Include API keys in output")
def config_list(ctx, show_secrets):
    """List all configuration"""
    # Check if hook function exists
    hook_name = "on_config_list"
    if app_hooks and hasattr(app_hooks, hook_name):
        # Call the hook with all parameters
        hook_func = getattr(app_hooks, hook_name)

        # Prepare arguments including global options
        kwargs = {}
        kwargs["command_name"] = "list"  # Pass command name for all commands

        kwargs["show_secrets"] = show_secrets

        # Add global options from context
        if ctx and ctx.obj:
            kwargs["debug"] = ctx.obj.get("debug", False)

        result = hook_func(**kwargs)
        return result
    else:
        # Default placeholder behavior
        click.echo("Executing list command...")

        click.echo(f"  show-secrets: {show_secrets}")


@main.group()
def tools():
    """🛠️  Manage CLI tools and extensions"""
    pass


@tools.command()
@click.pass_context
@click.argument("TOOL_NAME")
def enable(ctx, tool_name):
    """Enable a tool"""
    # Check if hook function exists
    hook_name = "on_tools_enable"
    if app_hooks and hasattr(app_hooks, hook_name):
        # Call the hook with all parameters
        hook_func = getattr(app_hooks, hook_name)

        # Prepare arguments including global options
        kwargs = {}
        kwargs["command_name"] = "enable"  # Pass command name for all commands

        kwargs["tool_name"] = tool_name

        # Add global options from context
        if ctx and ctx.obj:
            kwargs["debug"] = ctx.obj.get("debug", False)

        result = hook_func(**kwargs)
        return result
    else:
        # Default placeholder behavior
        click.echo("Executing enable command...")

        click.echo(f"  tool_name: {tool_name}")


@tools.command()
@click.pass_context
@click.argument("TOOL_NAME")
def disable(ctx, tool_name):
    """Disable a tool"""
    # Check if hook function exists
    hook_name = "on_tools_disable"
    if app_hooks and hasattr(app_hooks, hook_name):
        # Call the hook with all parameters
        hook_func = getattr(app_hooks, hook_name)

        # Prepare arguments including global options
        kwargs = {}
        kwargs["command_name"] = "disable"  # Pass command name for all commands

        kwargs["tool_name"] = tool_name

        # Add global options from context
        if ctx and ctx.obj:
            kwargs["debug"] = ctx.obj.get("debug", False)

        result = hook_func(**kwargs)
        return result
    else:
        # Default placeholder behavior
        click.echo("Executing disable command...")

        click.echo(f"  tool_name: {tool_name}")


@tools.command(name="list")
@click.pass_context
@click.option("--show-disabled", type=bool, default=False, help="Include disabled tools")
def tools_list(ctx, show_disabled):
    """List all tools"""
    # Check if hook function exists
    hook_name = "on_tools_list"
    if app_hooks and hasattr(app_hooks, hook_name):
        # Call the hook with all parameters
        hook_func = getattr(app_hooks, hook_name)

        # Prepare arguments including global options
        kwargs = {}
        kwargs["command_name"] = "list"  # Pass command name for all commands

        kwargs["show_disabled"] = show_disabled

        # Add global options from context
        if ctx and ctx.obj:
            kwargs["debug"] = ctx.obj.get("debug", False)

        result = hook_func(**kwargs)
        return result
    else:
        # Default placeholder behavior
        click.echo("Executing list command...")

        click.echo(f"  show-disabled: {show_disabled}")


def cli_entry():
    """Entry point for the CLI when installed via pipx."""
    # Load plugins before running the CLI
    load_plugins(main)
    main()


if __name__ == "__main__":
    cli_entry()
