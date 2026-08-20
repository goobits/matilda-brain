"""
Matilda Brain i18n Module
=========================

Internationalization support for Matilda Brain.

Usage:
    from matilda_brain.i18n import t, t_brain, t_common, set_language

    # Brain-specific translation (default domain)
    print(t("cli.name"))                      # "Brain"
    print(t("cli.tagline"))                   # "Talk to Transformer"

    # With interpolation
    print(t("errors.model_not_found", message="gpt-5 not available"))

    # Common domain (shared terms)
    print(t_common("status.ready"))           # "Ready"
    print(t_common("errors.not_found", item="Session"))

    # Change language
    set_language("es")
"""

from matilda_i18n import I18nLoader

# =============================================================================
# Brain-specific loader instance
# =============================================================================

_loader = I18nLoader(default_domain="brain")

# Primary translation function (defaults to brain domain)
t = _loader.t

# Domain-specific shortcuts
t_brain = _loader.t_domain("brain")
t_common = _loader.t_domain("common")

# Language management
set_language = _loader.set_language
get_language = _loader.get_language

# Re-export for convenience
__all__ = [
    "I18nLoader",
    "get_language",
    "set_language",
    "t",
    "t_brain",
    "t_common",
]
