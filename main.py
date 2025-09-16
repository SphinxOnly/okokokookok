import discord
from discord import app_commands
from discord.ext import commands
import re

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

TICKET_CATEGORY_ID = None  # Optional: Kategorie-ID für Tickets
TICKET_PANEL_CHANNEL_ID = 123456789012345678  # Hier ID des Ticket-Panels Channels
TICKET_BASENAME = "DaryoSupport"

pending_support_roles = {}

def get_next_ticket_number(guild: discord.Guild, base_name=TICKET_BASENAME):
    regex = re.compile(rf"^{re.escape(base_name)} - (\d+)$")
    numbers = []
    for channel in guild.text_channels:
        match = regex.match(channel.name)
        if match:
            numbers.append(int(match.group(1)))
    return max(numbers)+1 if numbers else 1

def parse_color(color_str: str) -> discord.Color:
    """Parse Farbname oder Hex-Code zu discord.Color, Standard: Blau."""
    color_str = color_str.lower()
    named_colors = {
        "default": discord.Color.default(),
        "teal": discord.Color.teal(),
        "dark_teal": discord.Color.dark_teal(),
        "green": discord.Color.green(),
        "dark_green": discord.Color.dark_green(),
        "blue": discord.Color.blue(),
        "dark_blue": discord.Color.dark_blue(),
        "purple": discord.Color.purple(),
        "dark_purple": discord.Color.dark_purple(),
        "magenta": discord.Color.magenta(),
        "dark_magenta": discord.Color.dark_magenta(),
        "gold": discord.Color.gold(),
        "dark_gold": discord.Color.dark_gold(),
        "orange": discord.Color.orange(),
        "dark_orange": discord.Color.dark_orange(),
        "red": discord.Color.red(),
        "dark_red": discord.Color.dark_red(),
        "lighter_grey": discord.Color.lighter_grey(),
        "dark_grey": discord.Color.dark_grey(),
        "light_grey": discord.Color.light_grey(),
        "darker_grey": discord.Color.darker_grey(),
        "blurple": discord.Color.blurple(),
        "greyple": discord.Color.greyple(),
        "dark_theme": discord.Color.dark_theme()
    }

    if color_str in named_colors:
        return named_colors[color_str]

    # Hex-Code (mit oder ohne #)
    if color_str.startswith("#"):
        color_str = color_str[1:]
    try:
        val = int(color_str, 16)
        if 0 <= val <= 0xFFFFFF:
            return discord.Color(val)
    except:
        pass
    # Fallback
    return discord.Color.blue()

# ---------- /msg Command ----------
@bot.tree.command(name="msg", description="Sende eine Nachricht mit flexiblen Optionen")
@app_commands.describe(
    title="Titel der Nachricht (Embed)",
    content="Inhalt der Nachricht",
    color="Farbe des Embeds (Name oder Hex, z.B. red, #ff0000)",
    channel="Kanal, in den die Nachricht gesendet wird",
    format="Format der Nachricht (embed, plain)"
)
async def msg(
    interaction: discord.Interaction,
    title: str,
    content: str,
    color: str = "blue",
    channel: discord.TextChannel = None,
    format: str = "embed"
):
    # Zielkanal bestimmen
    target_channel = channel or interaction.channel

    embed_color = parse_color(color)

    if format.lower() == "embed":
        embed = discord.Embed(title=title, description=content, color=embed_color)
        await target_channel.send(embed=embed)
        await interaction.response.send_message(f"Embed-Nachricht wurde in {target_channel.mention} gesendet.", ephemeral=True)
    elif format.lower() == "plain":
        msg = f"**{title}**\n{content}"
        await target_channel.send(msg)
        await interaction.response.send_message(f"Plain-Text Nachricht wurde in {target_channel.mention} gesendet.", ephemeral=True)
    else:
        await interaction.response.send_message(f"Unbekanntes Format: {format}. Bitte 'embed' oder 'plain' verwenden.", ephemeral=True)

# ---------- Ticket-Panel Command ----------
@bot.tree.command(name="ticketpanel", description="Erstellt das Ticket-Panel mit Button")
@app_commands.default_permissions(administrator=True)
async def ticketpanel(interaction: discord.Interaction):
    channel = bot.get_channel(TICKET_PANEL_CHANNEL_ID)
    if channel is None:
        await interaction.response.send_message("Ticket-Panel Channel nicht gefunden!", ephemeral=True)
        return

    embed = discord.Embed(
        title="Support Ticket System",
        description="Klicke auf den Button, um ein Support-Ticket zu eröffnen.",
        color=discord.Color.blurple()
    )
    button = TicketCreateButton()
    view = discord.ui.View()
    view.add_item(button)

    await channel.send(embed=embed, view=view)
    await interaction.response.send_message("Ticket-Panel wurde gepostet.", ephemeral=True)

# ---------- Button zum Ticket erstellen ----------
class TicketCreateButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Ticket erstellen", style=discord.ButtonStyle.green)

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        options = [
            discord.SelectOption(label=role.name, value=str(role.id))
            for role in guild.roles if role != guild.default_role
        ]

        if not options:
            await interaction.response.send_message("Keine Rollen verfügbar!", ephemeral=True)
            return

        select = SupportRoleSelect(options=options)
        view = discord.ui.View()
        view.add_item(select)

        await interaction.response.send_message("Wähle eine Support-Rolle aus:", view=view, ephemeral=True)

# ---------- Dropdown für Support-Rolle ----------
class SupportRoleSelect(discord.ui.Select):
    def __init__(self, options):
        super().__init__(
            placeholder="Wähle eine Support-Rolle aus...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        role_id = int(self.values[0])
        role = interaction.guild.get_role(role_id)
        if role is None:
            await interaction.response.send_message("Rolle nicht gefunden!", ephemeral=True)
            return

        pending_support_roles[interaction.user.id] = role

        await interaction.response.send_modal(TicketInfoModal())

# ---------- Modal für Titel + Inhalt + Farbe ----------
class TicketInfoModal(discord.ui.Modal, title="Ticket erstellen"):
    title_input = discord.ui.TextInput(
        label="Titel des Tickets",
        style=discord.TextStyle.short,
        max_length=100,
        placeholder="Gib den Titel deines Tickets ein",
    )
    content_input = discord.ui.TextInput(
        label="Inhalt des Tickets",
        style=discord.TextStyle.paragraph,
        max_length=1000,
        placeholder="Beschreibe dein Problem/Anliegen",
    )
    color_input = discord.ui.TextInput(
        label="Embed-Farbe (Name oder Hex, z.B. red, #ff0000)",
        style=discord.TextStyle.short,
        max_length=20,
        required=False,
        placeholder="Standard ist blau"
    )

    async def on_submit(self, interaction: discord.Interaction):
        user = interaction.user
        guild = interaction.guild

        if user.id not in pending_support_roles:
            await interaction.response.send_message("Support-Rolle nicht gefunden. Bitte starte den Prozess erneut.", ephemeral=True)
            return

        support_role = pending_support_roles.pop(user.id)

        ticket_number = get_next_ticket_number(guild)
        channel_name = f"{TICKET_BASENAME} - {ticket_number:02d}"

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            support_role: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }

        category = guild.get_channel(TICKET_CATEGORY_ID) if TICKET_CATEGORY_ID else None

        channel = await guild.create_text_channel(channel_name, overwrites=overwrites, category=category, reason=f"Ticket erstellt von {user}")

        embed_color = parse_color(self.color_input.value) if self.color_input.value else discord.Color.blue()
        embed = discord.Embed(title=self.title_input.value, description=self.content_input.value, color=embed_color)
        embed.set_footer(text=f"Ticket von {user.display_name}", icon_url=user.display_avatar.url)
        await channel.send(content=f"{user.mention} hat ein Ticket erstellt.", embed=embed)

        await interaction.response.send_message(f"Dein Ticket wurde erstellt: {channel.mention}", ephemeral=True)

@bot.event
async def on_ready():
    print(f"Bot online als {bot.user}!")
    try:
        await bot.tree.sync()
        print("Slash-Commands synchronisiert!")
    except Exception as e:
        print(f"Fehler beim Sync: {e}")

bot.run("DEIN_BOT_TOKEN_HIER")

