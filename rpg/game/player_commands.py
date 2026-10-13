"""Public command inventory shared by Telegram's menu and Help."""

PUBLIC_COMMANDS = (
    'start', 'location', 'map', 'journal', 'inventory', 'profile',
    'activities', 'stats', 'skills', 'build', 'settings', 'help',
)

# Compatibility and recovery commands remain available outside the short menu.
HELP_COMMANDS = PUBLIC_COMMANDS + ('go', 'enc', 'pvp', 'unstuck')
