import discord
from discord import app_commands
import json
import os
from datetime import datetime


intents = discord.Intents.default()
intents.members = True 
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

admin_roles = {"Admin", "Bot-Dev"}
moderator_roles = {"Admin", "Moderator", "Officer", "Bot-Dev"}
banker_roles = {"Rare Banker", "Bot-Dev"}
war = 133
shard = "Able"
side = "Warden"
regiment_tag = "NWO"

# Simple file-based persistence
BASE_DIR                    = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE                 = os.path.join(BASE_DIR, "config.json")
KILLS_LOSSES_FILE           = os.path.join(BASE_DIR, f"kills_losses_{regiment_tag}.json")
COSTS_FILE                  = os.path.join(BASE_DIR, "rareCosts.json")
ROLE_FILE                   = os.path.join(BASE_DIR, "roles.json")
CONTRIBUTIONS_FILE          = os.path.join(BASE_DIR, "contributions.json")
RARE_LOST_FILE              = os.path.join(BASE_DIR, "rare_lost.json")
RARE_BUILDS_FILE            = os.path.join(BASE_DIR, "rare_builds.json")
GOALS_FILE                  = os.path.join(BASE_DIR, "goals.json")
BANK_ACCOUNTS_FILE          = os.path.join(BASE_DIR, "bank_accounts.json")
BANK_LOG_FILE               = os.path.join(BASE_DIR, "bank_log.json")

def load_goals():
    """Return goals for the current war only: { pool: { item, cost } }"""
    if os.path.exists(GOALS_FILE):
        with open(GOALS_FILE, "r") as f:
            all_goals = json.load(f)
        return all_goals.get(str(war), {})
    return {}

def save_goals(goals):
    """Save goals for the current war, preserving other wars."""
    all_goals = {}
    if os.path.exists(GOALS_FILE):
        with open(GOALS_FILE, "r") as f:
            all_goals = json.load(f)
    all_goals[str(war)] = goals
    with open(GOALS_FILE, "w") as f:
        json.dump(all_goals, f)

# ── Bank accounts ────────────────────────────────────────────────────────────
# Structure: { banker_name: { location: { "rares": int, "alloys": int } } }

def load_bank_accounts() -> dict:
    """Return bank accounts for the current war only."""
    if os.path.exists(BANK_ACCOUNTS_FILE):
        with open(BANK_ACCOUNTS_FILE, "r") as f:
            all_accounts = json.load(f)
        # Legacy: if top-level keys look like banker names (not war numbers), treat as war 0
        if all_accounts and not all(k.isdigit() for k in all_accounts):
            return all_accounts if str(war) == "0" else {}
        return all_accounts.get(str(war), {})
    return {}

def save_bank_accounts(accounts: dict):
    """Save bank accounts for the current war, preserving other wars."""
    all_accounts = {}
    if os.path.exists(BANK_ACCOUNTS_FILE):
        with open(BANK_ACCOUNTS_FILE, "r") as f:
            all_accounts = json.load(f)
        # Migrate legacy flat format on first war-scoped save
        if all_accounts and not all(k.isdigit() for k in all_accounts):
            all_accounts = {}
    all_accounts[str(war)] = accounts
    with open(BANK_ACCOUNTS_FILE, "w") as f:
        json.dump(all_accounts, f, indent=2)

def load_bank_log() -> list:
    if os.path.exists(BANK_LOG_FILE):
        with open(BANK_LOG_FILE, "r") as f:
            log = json.load(f)
        return [e for e in log if str(e.get("war", war)) == str(war)]
    return []

def save_bank_log(log: list):
    # Merge with entries from other wars before saving
    all_log = []
    if os.path.exists(BANK_LOG_FILE):
        with open(BANK_LOG_FILE, "r") as f:
            all_log = json.load(f)
    # Remove current war's entries, then re-add the updated ones
    other_wars = [e for e in all_log if str(e.get("war", war)) != str(war)]
    with open(BANK_LOG_FILE, "w") as f:
        json.dump(other_wars + log, f, indent=2)

def append_bank_log(entry: dict):
    log = load_bank_log()
    entry["war"] = war
    entry["log_id"] = (max((e["log_id"] for e in log), default=0) + 1)
    log.append(entry)
    save_bank_log(log)

def bank_credit(accounts: dict, banker: str, location: str, rares: int, alloys: int):
    """Add rares/alloys to a banker's location slot (creates if missing)."""
    accounts.setdefault(banker, {})
    accounts[banker].setdefault(location, {"rares": 0, "alloys": 0})
    accounts[banker][location]["rares"]  += rares
    accounts[banker][location]["alloys"] += alloys

def bank_debit(accounts: dict, banker: str, location: str, rares: int, alloys: int) -> str | None:
    """
    Remove rares/alloys from a banker's location slot.
    Returns None on success, or an error string if balance is insufficient.
    """
    slot = accounts.get(banker, {}).get(location, {"rares": 0, "alloys": 0})
    if slot["rares"] < rares:
        return f"❌ Insufficient rares at **{location}**: have `{slot['rares']}`, need `{rares}`."
    if slot["alloys"] < alloys:
        return f"❌ Insufficient alloys at **{location}**: have `{slot['alloys']}`, need `{alloys}`."
    accounts[banker][location]["rares"]  -= rares
    accounts[banker][location]["alloys"] -= alloys
    # Clean up empty slots
    if accounts[banker][location]["rares"] == 0 and accounts[banker][location]["alloys"] == 0:
        del accounts[banker][location]
    if not accounts[banker]:
        del accounts[banker]
    return None

with open(COSTS_FILE, "r") as f:
    RARE_COSTS = json.load(f)

def load_kills_losses():
    if os.path.exists(KILLS_LOSSES_FILE):
        with open(KILLS_LOSSES_FILE, "r") as f:
            return json.load(f)
    return []

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return []

def set_config():
    global war, shard, side, regiment_tag, KILLS_LOSSES_FILE
    config = load_config()
    if not config:
        return
    data = config[0]
    war = data['war']
    shard = data['shard']
    side = data['side']
    regiment_tag = data['regiment_tag']
    KILLS_LOSSES_FILE = os.path.join(BASE_DIR, f"kills_losses_{regiment_tag}.json")
    return []

def init_roles():
    """Create roles.json from in-memory defaults if it doesn't exist."""
    if not os.path.exists(ROLE_FILE):
        default_roles = [{"role": r} for r in moderator_roles]
        save_roles(default_roles)
        print(f"Created {ROLE_FILE} with default roles: {moderator_roles}")
    set_roles()

def load_roles():
    if os.path.exists(ROLE_FILE):
        with open(ROLE_FILE, "r") as f:
            return json.load(f)
    return []

def set_roles():
    global moderator_roles
    roles_data = load_roles() 
    if not roles_data:
        return
    moderator_roles = {entry['role'] for entry in roles_data}

def save_kills_losses(entries):
    with open(KILLS_LOSSES_FILE, "w") as f:
        json.dump(entries, f)

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f)

def save_roles(roles):
    with open(ROLE_FILE, "w") as f:
        json.dump(roles, f)

def next_id(kills):
    if not kills:
        return 1
    return max(k["id"] for k in kills) + 1

async def cost_autocomplete(interaction: discord.Interaction, current: str):
    seen = set()
    choices = []
    for item in RARE_COSTS:
        for label in [item["Name"]]:
            if label not in seen and current.lower() in label.lower():
                seen.add(label)
                choices.append(app_commands.Choice(name=label, value=label))
    return choices[:5]  # Discord limits autocomplete to 25 results

async def kill_autocomplete(interaction: discord.Interaction, current: str):
    seen = set()
    choices = []
    for item in RARE_COSTS:
        for label in [item["Name"]]:
            if label not in seen and current.lower() in label.lower():
                seen.add(label)
                choices.append(app_commands.Choice(name=label, value=label))
    return choices[:5]

async def shard_autocomplete(interaction: discord.Interaction, current: str):
    choices = ["Able", "Charlie"]
    return [
        app_commands.Choice(name=s, value=s)
        for s in choices if current.lower() in s.lower()
    ]

async def side_autocomplete(interaction: discord.Interaction, current: str):
    choices = ["Colonial", "Warden"]
    return [
        app_commands.Choice(name=s, value=s)
        for s in choices if current.lower() in s.lower()
    ]

async def currentmodRoles_autocomplete(interaction: discord.Interaction, current: str):
    choices = moderator_roles
    return [
        app_commands.Choice(name=s, value=s)
        for s in choices if current.lower() in s.lower()
    ]

async def serverRoles_autocomplete(interaction: discord.Interaction, current: str):
    if not interaction.guild:
        return []
    return [
        app_commands.Choice(name=role.name, value=role.name)
        for role in interaction.guild.roles
        if current.lower() in role.name.lower() and role.name != "@everyone"
    ][:5]

fkt = app_commands.Group(name="fkt", description="The main FKT bot")

@fkt.command(name="help", description="Show all FKT (Foxhole Kill-Rare Tracker) Bot command categories")
async def main_help(interaction: discord.Interaction):
    help_text = (
        "**Welcome to the FKT Bot!**\n\n"
        
        "**📊 Tracker**\n"
        "Kill & Loss logging with rare cost tracking\n"
        "`/tracker help` — Full tracker commands\n\n"
        
        "**💎 Rares System**\n"
        "Contribution tracking, voting, goals, and builds\n"
        "`/rares help` — Full rare commands\n\n"
        
        "**🏦 Bank System**\n"
        "Personal banker inventory, deposits, handovers & spending\n"
        "`/bank help` — Full banking commands\n\n"
        
        "**⚙️ Config & Admin**\n"
        "War settings, permissions, and bot configuration\n"
        "`/config_fkt help` — Config commands\n\n"
        
        "**Quick Start:**\n"
        "1. Use `/rares contribution` if you have rares to contribute\n"
        "2. Bankers confirm the contributions and use use banking commands between each oher\n"
        "3. Log vehicle kills and losses with `/tracker kill` or `/tracker lost`\n"
    )

    embed = discord.Embed(
        title="FKT Bot - Command Overview",
        description=help_text,
        color=discord.Color.teal()
    )
    embed.set_footer(text="Made by Darkenson • Use the sub-help commands for details")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

tree.add_command(fkt)


config_fkt = app_commands.Group(name="config_fkt", description="Configure commands for the bot")

@config_fkt.command(name="help", description="List all FKT config commands")
async def fkt_help(interaction: discord.Interaction):
    help_text = (
        "⚙️ **Config Commands Help**\n\n"
        "`/config_fkt config` — Set the active war, shard, side, and regiment tag (Admin only)\n"
        "`/config_fkt add_perms` — Give a role moderator permissions (Admin only)\n"
        "`/config_fkt remove_perms` — Remove moderator permissions from a role (Admin only)\n"
        "`/config_fkt clear_kill_list` — Wipe the entire kill/loss record (Admin only)\n\n"
        
        "**Useful Tip:**\n"
        "• Use `/config_fkt config` when a new war begins."
    )

    embed = discord.Embed(
        title="FKT Config System",
        description=help_text,
        color=discord.Color.dark_gray()
    )
    embed.set_footer(text="Made by Darkenson")

    await interaction.response.send_message(embed=embed, ephemeral=True)

@config_fkt.command(name="config", description="Configure the bot - war, shard and side you're on")
@app_commands.describe(war="The war number you wish to see info on or log info for")
@app_commands.describe(shard="The shard you play on")
@app_commands.describe(side="The side your regiment played on")
@app_commands.describe(regiment_tag="Your regiment tag")
@app_commands.autocomplete(shard=shard_autocomplete)
@app_commands.autocomplete(side=side_autocomplete)
async def config(interaction: discord.Interaction, war: str, shard: str, side: str, regiment_tag: str):
    user_roles = {role.name for role in interaction.user.roles}
    is_privileged = bool(user_roles.intersection(admin_roles))
    if not is_privileged:
        await interaction.response.send_message(
            f"❌ Only admins can change moderator permissions.",
            ephemeral=True
        )
        return

    config = load_config()
    config = []
    config.append({
        "war": war,
        "shard": shard,
        "side": side,
        "regiment_tag": regiment_tag
    })
    save_config(config)
    set_config()
    await interaction.response.send_message(
        f"✅ Config has been changed. Data is loaded and saved for regiment {regiment_tag}, for war **{war}**, {shard} shard, on the {side} side."
    )

@config_fkt.command(name="add_perms", description="Give a role moderator permissions")
@app_commands.describe(role="The role you'd like moderator permissions for")
@app_commands.autocomplete(role=serverRoles_autocomplete)
async def role_add(interaction: discord.Interaction, role: str):
    user_roles = {role.name for role in interaction.user.roles}
    is_privileged = bool(user_roles.intersection(admin_roles))
    if not is_privileged:
        await interaction.response.send_message(
            f"❌ Only admins can change moderator permissions.",
            ephemeral=True
        )
        return
    roles = load_roles()
    roles.append({"role": role})
    save_roles(roles)
    set_roles()
    await interaction.response.send_message(
        f"✅ Moderator roles have been changed. Mod roles are currently {moderator_roles}."
    )

@config_fkt.command(name="remove_perms", description="Remove moderator permissions from a role")
@app_commands.describe(role="The role to remove moderator permissions from")
@app_commands.autocomplete(role=currentmodRoles_autocomplete)
async def role_remove(interaction: discord.Interaction, role: str):
    user_roles = {r.name for r in interaction.user.roles}
    is_privileged = bool(user_roles.intersection(admin_roles))
    if not is_privileged:
        await interaction.response.send_message(
            "❌ Only admins can change moderator permissions.",
            ephemeral=True
        )
        return

    roles = load_roles()
    updated = [entry for entry in roles if entry["role"] != role]

    if len(updated) == len(roles):
        await interaction.response.send_message(
            f"⚠️ Role `{role}` was not found in the moderator list.",
            ephemeral=True
        )
        return

    save_roles(updated)
    set_roles()
    await interaction.response.send_message(
        f"✅ Removed `{role}` from moderator roles. Mod roles are now: {moderator_roles}."
    )

@config_fkt.command(name="clear_kill_list", description="Clear all kills and losses")
async def clear_kills(interaction: discord.Interaction):
    user_roles = {role.name for role in interaction.user.roles}
    if not bool(user_roles.intersection(admin_roles)):
        await interaction.response.send_message("❌ Only admins can clear the kill/loss list.", ephemeral=True)
        return
    save_kills_losses([])
    await interaction.response.send_message("🗑️ Kill and loss list cleared.")

tree.add_command(config_fkt)


# Create a command group: /tracker
tracker = app_commands.Group(name="tracker", description="Track kills and losses in Foxhole")

@tracker.command(name="help", description="List all tracker commands")
async def tracker_help(interaction: discord.Interaction):
    help_text = (
        "📊 **Kill & Loss Tracker Help**\n\n"
        "`/tracker kill` — Log a vehicle or structure you destroyed\n"
        "`/tracker lost` — Log a vehicle or structure your regiment lost\n"
        "`/tracker remove` — Remove a specific kill or loss by ID\n"
        "`/tracker list` — View all logged kills and losses\n"
        "`/tracker report` — Show net rare/alloy cost summary (kills vs losses)\n\n"
        
        "**Note:**\n"
        "• You can only remove your own entries (or moderators can remove any)."
    )

    embed = discord.Embed(
        title="Kill & Loss Tracker",
        description=help_text,
        color=discord.Color.red()
    )
    embed.set_footer(text="Made by Darkenson")

    await interaction.response.send_message(embed=embed, ephemeral=True)

@tracker.command(name="kill", description="Log a kill")
@app_commands.describe(target="What was killed (e.g. Frigate)")
@app_commands.autocomplete(target=kill_autocomplete)
async def log_kill(interaction: discord.Interaction, target: str):
    entries = load_kills_losses()
    entry_id = next_id(entries)

    match = next((item for item in RARE_COSTS if item["Name"].lower() == target.lower()), None)
    cost_note = f" (💎 `{match['Rares']}` rares)" if match else " ⚠️ *(not in rare cost list)*"

    entries.append({
        "id": entry_id,
        "type": "kill",
        "target": target,
        "user": interaction.user.name,
        "timestamp": str(interaction.created_at),
        "war": war,
        "shard": shard
    })
    save_kills_losses(entries)
    await interaction.response.send_message(
        f"✅ Kill logged: **{target}**{cost_note} (ID: `{entry_id}`) by {interaction.user.name}"
    )

@tracker.command(name="lost", description="Log a loss")
@app_commands.describe(target="What was lost (e.g. Frigate)")
@app_commands.autocomplete(target=kill_autocomplete)
async def log_loss(interaction: discord.Interaction, target: str):
    entries = load_kills_losses()
    entry_id = next_id(entries)

    match = next((item for item in RARE_COSTS if item["Name"].lower() == target.lower()), None)
    cost_note = f" (💎 `{match['Rares']}` rares)" if match else " ⚠️ *(not in rare cost list)*"

    entries.append({
        "id": entry_id,
        "type": "loss",
        "target": target,
        "user": interaction.user.name,
        "timestamp": str(interaction.created_at),
        "war": war,
        "shard": shard
    })
    save_kills_losses(entries)
    await interaction.response.send_message(
        f"📉 Loss logged: **{target}**{cost_note} (ID: `{entry_id}`) by {interaction.user.name}"
    )

@tracker.command(name="list", description="List all logged kills and losses for the current war")
async def list_kills(interaction: discord.Interaction):
    entries = load_kills_losses()
    kills = [e for e in entries if e.get("type") == "kill" and e["war"] == war]
    losses = [e for e in entries if e.get("type") == "loss" and e["war"] == war]

    if not kills and not losses:
        await interaction.response.send_message(f"📋 No entries logged for war {war}.")
        return

    lines = []
    if kills:
        lines.append(f"⚔️ **Kills (war {war}):**")
        for k in kills:
            ts = datetime.fromisoformat(k["timestamp"]).strftime("%Y-%m-%d %H:%M")
            lines.append(f"  `#{k['id']}` **{k['target']}** — by {k['user']} at {ts}")

    if losses:
        lines.append(f"\n📉 **Losses (war {war}):**")
        for l in losses:
            ts = datetime.fromisoformat(l["timestamp"]).strftime("%Y-%m-%d %H:%M")
            lines.append(f"  `#{l['id']}` **{l['target']}** — by {l['user']} at {ts}")

    await interaction.response.send_message("\n".join(lines))


@tracker.command(name="remove", description="Remove a kill or loss entry by ID")
@app_commands.describe(entry_id="The ID of the entry to remove")
async def remove_entry(interaction: discord.Interaction, entry_id: int):
    entries = load_kills_losses()
    match = next((e for e in entries if e["id"] == entry_id), None)

    if not match:
        await interaction.response.send_message(f"❌ No entry found with ID `{entry_id}`.", ephemeral=True)
        return

    user_roles = {role.name for role in interaction.user.roles}
    is_privileged = bool(user_roles.intersection(moderator_roles))
    is_reporter = match["user"] == interaction.user.name

    if not is_privileged and not is_reporter:
        await interaction.response.send_message(
            f"❌ You can't remove entry `#{entry_id}`. Only the original reporter ({match['user']}) or a moderator can.",
            ephemeral=True
        )
        return

    entries = [e for e in entries if e["id"] != entry_id]
    save_kills_losses(entries)
    type_label = "Kill" if match["type"] == "kill" else "Loss"
    await interaction.response.send_message(f"🗑️ Removed {type_label} `#{entry_id}`: **{match['target']}**")

@tracker.command(name="report", description="Show total rare costs for all kills and losses")
async def cost_report(interaction: discord.Interaction):
    entries = load_kills_losses()
    kills  = [e for e in entries if e.get("type") == "kill"]
    losses = [e for e in entries if e.get("type") == "loss"]

    # KILLS
    # Tally up kills by target name (case-insensitive)
    tally_kills = {}
    unrecognized_kills = []

    for kill in kills:
        target = kill["target"]
        target_lower = target.lower()

        # Find a match in RARE_COSTS by Name
        match = next(
            (item for item in RARE_COSTS
             if item["Name"].lower() == target_lower),
            None
        )

        if match:
            key = match["Name"]
            if key not in tally_kills:
                tally_kills[key] = {"count": 0, "rares": 0, "alloys": 0}
            tally_kills[key]["count"] += 1
            tally_kills[key]["rares"] += match["Rares"]
            tally_kills[key]["alloys"] += match["Alloys"]
        else:
            unrecognized_kills.append(target)

    if not tally_kills:
        await interaction.response.send_message("No kills matched any known items in the rare cost list.")
        return

    # Sort by total rares descending
    sorted_kill_tally = sorted(tally_kills.items(), key=lambda x: x[1]["rares"], reverse=True)

    total_kill_rares = sum(v["rares"] for v in tally_kills.values())
    total_kill_alloys = sum(v["alloys"] for v in tally_kills.values())

    lines = ["📋 **Kill Cost Summary**\n"]
    for name, data in sorted_kill_tally:
        lines.append(
            f"**{name}** x{data['count']} — "
            f"🪨 `{data['alloys']}` alloys | 💎 `{data['rares']}` rares"
        )

    lines.append(f"\n**Total killed: 🪨 `{total_kill_alloys}` alloys | 💎 `{total_kill_rares}` rares**")

    if unrecognized_kills:
        lines.append(f"\n⚠️ Unrecognized (not in cost list): {', '.join(f'`{u}`' for u in unrecognized_kills)}")

    # LOSSES
    # Tally up losses by target name (case-insensitive)
    tally_losses = {}
    unrecognized_losses = []

    for loss in losses:
        target = loss["target"]
        target_lower = target.lower()

        # Find a match in RARE_COSTS by Name
        match = next(
            (item for item in RARE_COSTS
             if item["Name"].lower() == target_lower),
            None
        )

        if match:
            key = match["Name"]
            if key not in tally_losses:
                tally_losses[key] = {"count": 0, "rares": 0, "alloys": 0}
            tally_losses[key]["count"] += 1
            tally_losses[key]["rares"] += match["Rares"]
            tally_losses[key]["alloys"] += match["Alloys"]
        else:
            unrecognized_losses.append(target)

    if not tally_losses:
        await interaction.response.send_message("No kills matched any known items in the rare cost list.")
        return

    # Sort by total rares descending
    sorted_losses_tally = sorted(tally_losses.items(), key=lambda x: x[1]["rares"], reverse=True)

    total_losses_rares = sum(v["rares"] for v in tally_losses.values())
    total_losses_alloys = sum(v["alloys"] for v in tally_losses.values())

    lines.append("~~            ~~\n")
    lines.append("💀 **Loss Cost Summary**\n")
    for name, data in sorted_losses_tally:
        lines.append(
            f"**{name}** x{data['count']} — "
            f"🪨 `{data['alloys']}` alloys | 💎 `{data['rares']}` rares"
        )

    lines.append(f"\n**Total lost: 🪨 `{total_losses_alloys}` alloys | 💎 `{total_losses_rares}` rares**")

    if unrecognized_losses:
        lines.append(f"\n⚠️ Unrecognized (not in cost list): {', '.join(f'`{u}`' for u in unrecognized_losses)}")
    

    # TOTAL
    lines.append("~~            ~~\n")
    lines.append(f"📋**Net: 🪨 `{(total_kill_alloys-total_losses_alloys)}` alloys | 💎 `{(total_kill_rares-total_losses_rares)}` rares**")

    await interaction.response.send_message("\n".join(lines))

tree.add_command(tracker)


# RARE BANKING MODULE

rares = app_commands.Group(name="rares", description="Track rare material banking and vehicle building events in Foxhole")

# ============================================================
# POOL DEFINITIONS
# "Aircraft" and "Ship" map to their rareCosts.json categories.
# "General" is an unrestricted wildcard pool.
# ============================================================

POOL_CATEGORIES = {
    "Aircraft": "Aircraft",
    "Ship":     "Ship",
    "General":  None,   # wildcard — accepts contributions towards anything
}

def items_for_pool(pool: str) -> list[dict]:
    """Return all RARE_COSTS items (Rares > 0) that belong to the given pool."""
    category = POOL_CATEGORIES.get(pool)
    if category is None:
        # General pool — return all items with rares > 0
        return [i for i in RARE_COSTS if i.get("Rares", 0) > 0]
    return [i for i in RARE_COSTS if i.get("Category") == category and i.get("Rares", 0) > 0]

# ============================================================
# PERSISTENCE HELPERS
# ============================================================

def load_contributions():
    if os.path.exists(CONTRIBUTIONS_FILE):
        with open(CONTRIBUTIONS_FILE, "r") as f:
            all_data = json.load(f)
        return [c for c in all_data if str(c.get("war", war)) == str(war)]
    return []

def save_contributions(contributions):
    all_data = []
    if os.path.exists(CONTRIBUTIONS_FILE):
        with open(CONTRIBUTIONS_FILE, "r") as f:
            all_data = json.load(f)
    other_wars = [c for c in all_data if str(c.get("war", war)) != str(war)]
    with open(CONTRIBUTIONS_FILE, "w") as f:
        json.dump(other_wars + contributions, f)

def load_rare_lost():
    if os.path.exists(RARE_LOST_FILE):
        with open(RARE_LOST_FILE, "r") as f:
            all_data = json.load(f)
        return [l for l in all_data if str(l.get("war", war)) == str(war)]
    return []

def save_rare_lost(lost):
    all_data = []
    if os.path.exists(RARE_LOST_FILE):
        with open(RARE_LOST_FILE, "r") as f:
            all_data = json.load(f)
    other_wars = [l for l in all_data if str(l.get("war", war)) != str(war)]
    with open(RARE_LOST_FILE, "w") as f:
        json.dump(other_wars + lost, f)

def load_rare_builds():
    if os.path.exists(RARE_BUILDS_FILE):
        with open(RARE_BUILDS_FILE, "r") as f:
            all_data = json.load(f)
        return [b for b in all_data if str(b.get("war", war)) == str(war)]
    return []

def save_rare_builds(builds):
    all_data = []
    if os.path.exists(RARE_BUILDS_FILE):
        with open(RARE_BUILDS_FILE, "r") as f:
            all_data = json.load(f)
    other_wars = [b for b in all_data if str(b.get("war", war)) != str(war)]
    with open(RARE_BUILDS_FILE, "w") as f:
        json.dump(other_wars + builds, f)

# ============================================================
# AUTOCOMPLETE HELPERS
# ============================================================

async def pool_autocomplete(interaction: discord.Interaction, current: str):
    """Three fixed pools: Aircraft, Ship, General."""
    return [
        app_commands.Choice(name=p, value=p)
        for p in POOL_CATEGORIES
        if current.lower() in p.lower()
    ]

async def goal_item_autocomplete(interaction: discord.Interaction, current: str):
    category = interaction.namespace.category
    if category == "General":
        # Items NOT in Aircraft or Ship
        items = [i["Name"] for i in RARE_COSTS if i.get("Category") not in ["Aircraft", "Ship"] and i.get("Rares", 0) > 0]
    else:
        # Items matching specific category
        items = [i["Name"] for i in RARE_COSTS if i.get("Category") == category and i.get("Rares", 0) > 0]
    
    return [app_commands.Choice(name=i, value=i) for i in items if current.lower() in i.lower()][:5]

async def vote_autocomplete(interaction: discord.Interaction, current: str):
    """Items in the pool already chosen by the user, plus an 'Any' option."""
    pool = interaction.namespace.pool or ""
    pool_items = items_for_pool(pool) if pool in POOL_CATEGORIES else []
    choices = [app_commands.Choice(name="Any", value="Any")]
    choices += [
        app_commands.Choice(name=item["Name"], value=item["Name"])
        for item in pool_items
        if current.lower() in item["Name"].lower()
    ]
    return choices[:5]

async def rare_cost_item_autocomplete(interaction: discord.Interaction, current: str):
    """For /rares build: only show items that have at least one vote."""
    contributions = load_contributions()
    voted_items = {
        c["vote"] for c in contributions
        if c.get("vote") and c["vote"] != "Any"
    }
    choices = []
    for item in RARE_COSTS:
        if item["Name"] in voted_items and current.lower() in item["Name"].lower():
            choices.append(app_commands.Choice(name=item["Name"], value=item["Name"]))
    return choices[:5]

async def guild_member_autocomplete(interaction: discord.Interaction, current: str):
    if not interaction.guild:
        return []
    return [
        app_commands.Choice(
            name=member.display_name,
            value=member.display_name
        )
        for member in interaction.guild.members
        if current.lower() in member.display_name.lower()
        and not member.bot
    ][:5]

# ============================================================
# HELP COMMAND
# ============================================================

@rares.command(name="help", description="List all rare material commands")
async def rares_help(interaction: discord.Interaction):
    help_text = (
        "💎 **Rare Materials System Help**\n\n"
        "**General**\n"
        "`/rares cost` — Look up rare and alloy cost of an item\n"
        "`/rares report` — Full overview of contributions, goals, builds & losses\n"
        "`/rares leaderboard` — Top rare contributors\n\n"

        "**Contribution**\n"
        "`/rares contribution` — Submit rares for a banker to confirm\n"
        "`/rares list` — View all rare contributions\n\n"

        "**Officer / Mod Commands**\n"
        "`/rares goal` — Set a goal for Aircraft / Ship / General pool\n"
        "`/rares votes` — See vote counts per item\n"
        "`/rares build` — Log a vehicle built with rares\n"
        "`/rares build_status` — Update vehicle status or assigned player\n"
        "`/rares lost` — Log lost or stolen rares\n"
        "`/rares remove_contribution` — Remove a contribution (Banker only)\n\n"

        "**Banking**\n"
        "Use `/bank help` for all banking commands (deposit, handover, spend, etc.)"
    )

    embed = discord.Embed(
        title="Rare Contribution System",
        description=help_text,
        color=discord.Color.gold()
    )
    embed.set_footer(text="Made by Darkenson")

    await interaction.response.send_message(embed=embed, ephemeral=True)

# ============================================================
# COST LOOKUP
# ============================================================

@rares.command(name="cost", description="Look up the rare and alloy cost of an item")
@app_commands.describe(name="Item name")
@app_commands.autocomplete(name=cost_autocomplete)
async def cost_lookup(interaction: discord.Interaction, name: str):
    matches = [
        item for item in RARE_COSTS
        if item["Name"].lower() == name.lower()
    ]
    if not matches:
        await interaction.response.send_message(f"❌ No item found matching `{name}`. Please pick from the autocomplete.", ephemeral=True)
        return
    lines = []
    for item in matches:
        lines.append(
            f"**{item['Name']}**\n"
            f"  🪨 Alloys: `{item['Alloys']}` | 💎 Rares: `{item['Rares']}`"
        )
    await interaction.response.send_message("\n\n".join(lines))

# RARE GOAL COMMAND

@rares.command(name="goal", description="Set a regiment goal for a specific item")
@app_commands.describe(category="The pool category", item="The specific item to target")
@app_commands.autocomplete(category=pool_autocomplete)
@app_commands.autocomplete(item=goal_item_autocomplete)
async def set_goal(interaction: discord.Interaction, category: str, item: str):
    user_roles = {r.name for r in interaction.user.roles}
    if not user_roles.intersection(moderator_roles):
        await interaction.response.send_message("❌ Only officers can set goals.", ephemeral=True)
        return

    match = next((i for i in RARE_COSTS if i["Name"] == item), None)
    if not match:
        await interaction.response.send_message("❌ Invalid item.", ephemeral=True)
        return

    goals = load_goals()
    goals[category] = {"item": item, "cost": match["Rares"]}
    save_goals(goals)
    
    await interaction.response.send_message(f"🎯 **Goal Set!** The {category} pool is now targeting: **{item}** (💎 `{match['Rares']}` rares).")

@rares.command(name="votes", description="See how many individual votes each item has received")
async def show_votes(interaction: discord.Interaction):
    user_roles = {r.name for r in interaction.user.roles}
    if not user_roles.intersection(moderator_roles):
        await interaction.response.send_message("❌ Only officers can view vote tallies.", ephemeral=True)
        return

    contributions = load_contributions()
    vote_counts = {}
    for c in contributions:
        v = c.get("vote", "Any")
        if v != "Any":
            vote_counts[v] = vote_counts.get(v, 0) + 1

    if not vote_counts:
        await interaction.response.send_message("No votes have been cast yet.")
        return

    sorted_votes = sorted(vote_counts.items(), key=lambda x: x[1], reverse=True)
    lines = ["🗳️ **Item Vote Tallies (1 vote per contribution):**"]
    for item, count in sorted_votes:
        lines.append(f"• **{item}**: `{count}` votes")
    
    await interaction.response.send_message("\n".join(lines))

@rares.command(name="voted_contributions", description="Show how many rares each member has put towards each of their votes")
async def show_voted_contributions(interaction: discord.Interaction):
    user_roles = {r.name for r in interaction.user.roles}
    if not user_roles.intersection(moderator_roles):
        await interaction.response.send_message("❌ Only officers can view voted contribution tallies.", ephemeral=True)
        return

    contributions = load_contributions()

    # Only count contributions with a specific vote (not "Any")
    voted = [c for c in contributions if c.get("vote") and c["vote"] != "Any"]

    if not voted:
        await interaction.response.send_message("No voted contributions have been logged yet.")
        return

    # Build: { player: { vote: total_rares } }
    tally: dict[str, dict[str, int]] = {}
    for c in voted:
        player = c["player"]
        vote   = c["vote"]
        amount = c.get("amount", 0)
        tally.setdefault(player, {})
        tally[player][vote] = tally[player].get(vote, 0) + amount

    # Sort players by their grand total (descending)
    sorted_players = sorted(tally.items(), key=lambda x: sum(x[1].values()), reverse=True)

    lines = ["🗳️ **Voted Rare Contributions (rares per vote per member):**\n"]
    for player, votes in sorted_players:
        player_total = sum(votes.values())
        lines.append(f"**{player}** — 💎 `{player_total}` rares across voted contributions")
        # Sort each player's votes by rares descending
        for vote_item, total in sorted(votes.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"  • **{vote_item}**: 💎 `{total}` rares")
        lines.append("")

    await interaction.response.send_message("\n".join(lines))

# ============================================================
# RARE CONTRIBUTION COMMANDS
# ============================================================

class ContributionConfirmView(discord.ui.View):
    """
    Shown after a user submits /rares contribution.
    Only a Rare Banker can press 'Received' or 'Deny'.
    The view stays active for 24 hours.
    """

    def __init__(self, contributor: str, amount: int, pool: str, vote: str, submitted_at: str):
        super().__init__(timeout=86400)  # 24 hours
        self.contributor  = contributor
        self.amount       = amount
        self.pool         = pool
        self.vote         = vote
        self.submitted_at = submitted_at

    def _is_banker(self, interaction: discord.Interaction) -> bool:
        user_roles = {r.name for r in interaction.user.roles}
        return bool(user_roles.intersection(banker_roles))

    @discord.ui.button(label="✅ Received", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._is_banker(interaction):
            await interaction.response.send_message(
                "❌ Only Rare Bankers can confirm contributions.", ephemeral=True
            )
            return

        contributions = load_contributions()
        contributions.append({
            "id":         next_id(contributions),
            "player":     self.contributor,
            "amount":     self.amount,
            "pool":       self.pool,
            "vote":       self.vote,
            "logged_by":  interaction.user.name,
            "war":        war,
            "timestamp":  self.submitted_at
        })
        save_contributions(contributions)

        # ── Auto-credit the confirming banker's "loose" account ──────────────
        banker_name = interaction.user.name
        accounts    = load_bank_accounts()
        bank_credit(accounts, banker_name, "loose", self.amount, 0)
        save_bank_accounts(accounts)
        append_bank_log({
            "op":        "contribution_received",
            "banker":    banker_name,
            "from":      self.contributor,
            "location":  "loose",
            "rares":     self.amount,
            "alloys":    0,
            "timestamp": str(interaction.created_at),
        })

        embed = interaction.message.embeds[0]
        embed.color = discord.Color.green()
        embed.set_footer(text=f"✅ Received & confirmed by {interaction.user.name}")
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="❌ Deny", style=discord.ButtonStyle.danger)
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._is_banker(interaction):
            await interaction.response.send_message(
                "❌ Only Rare Bankers can deny contributions.", ephemeral=True
            )
            return

        embed = interaction.message.embeds[0]
        embed.color = discord.Color.red()
        embed.set_footer(text=f"❌ Denied by {interaction.user.name}")
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(embed=embed, view=self)


@rares.command(name="contribution", description="Submit rares you've deposited for a banker to confirm")
@app_commands.describe(
    amount="How many rares you deposited",
    pool="Which pool are these rares going into: Aircraft, Ship, or General",
    vote="Which specific item you'd like to vote to build (or 'Any')"
)
@app_commands.autocomplete(pool=pool_autocomplete)
@app_commands.autocomplete(vote=vote_autocomplete)
async def rare_contribution(interaction: discord.Interaction, amount: int, pool: str, vote: str):
    if amount <= 0:
        await interaction.response.send_message("❌ Amount must be a positive number.", ephemeral=True)
        return

    if pool not in POOL_CATEGORIES:
        await interaction.response.send_message(
            f"❌ `{pool}` is not a valid pool. Choose Aircraft, Ship, or General.",
            ephemeral=True
        )
        return

    # Validate vote is either "Any" or a real item in that pool
    if vote != "Any":
        pool_items = items_for_pool(pool)
        if not any(i["Name"].lower() == vote.lower() for i in pool_items):
            await interaction.response.send_message(
                f"❌ `{vote}` is not a valid item for the **{pool}** pool. Use the autocomplete to pick a valid item.",
                ephemeral=True
            )
            return

    contributor  = interaction.user.name
    submitted_at = str(interaction.created_at)

    embed = discord.Embed(
        title="💎 Rare Contribution — Pending Confirmation",
        color=discord.Color.yellow(),
        timestamp=interaction.created_at
    )
    embed.add_field(name="Contributor", value=contributor,             inline=True)
    embed.add_field(name="Amount",      value=f"💎 `{amount}` rares",  inline=True)
    embed.add_field(name="Pool",        value=pool,                    inline=True)
    embed.add_field(name="Vote",        value=vote,                    inline=True)
    embed.set_footer(text="⏳ Awaiting confirmation from a Rare Banker")

    view = ContributionConfirmView(
        contributor  = contributor,
        amount       = amount,
        pool         = pool,
        vote         = vote,
        submitted_at = submitted_at,
    )

    await interaction.response.send_message(embed=embed, view=view)

@rares.command(name="remove_contribution", description="Remove a rare contribution entry by ID")
@app_commands.describe(entry_id="The ID of the contribution to remove")
async def rare_contribution_remove(interaction: discord.Interaction, entry_id: int):
    # Permission check: Only Bankers (and Bot-Devs)
    user_roles = {r.name for r in interaction.user.roles}
    if not user_roles.intersection(banker_roles):
        await interaction.response.send_message("❌ Only rare bankers can remove contributions.", ephemeral=True)
        return

    contributions = load_contributions()
    match = next((c for c in contributions if c["id"] == entry_id), None)

    if not match:
        await interaction.response.send_message(f"❌ No contribution found with ID `{entry_id}`.", ephemeral=True)
        return

    # Filter out the specific ID
    updated_contributions = [c for c in contributions if c["id"] != entry_id]
    save_contributions(updated_contributions)
    
    await interaction.response.send_message(
        f"🗑️ Removed contribution `#{entry_id}`: **{match['amount']}** rares from **{match['player']}** (Pool: {match.get('pool','?')} | Vote: {match.get('vote','?')})"
    )

@rares.command(name="list", description="List rare contributions with optional filters")
@app_commands.describe(
    mine="If True, only shows contributions where you are the contributor or the banker"
)
async def rare_contribution_list(interaction: discord.Interaction, mine: bool = False):
    contributions = load_contributions()

    if not contributions:
        await interaction.response.send_message("No contributions logged yet.", ephemeral=True)
        return

    display_list = contributions
    active_filters = []

    if mine:
        current_user = interaction.user.name
        display_list = [
            c for c in display_list
            if c["player"] == current_user or c["logged_by"] == current_user
        ]
        active_filters.append("Your Involvement")

    if not display_list:
        filter_str = " and ".join(active_filters)
        await interaction.response.send_message(f"No contributions found matching: **{filter_str}**", ephemeral=True)
        return

    header_suffix = f" ({', '.join(active_filters)})" if active_filters else ""
    lines = [f"💎 **Rare Contributions{header_suffix}:**\n"]
    total_rares = 0

    for c in display_list:
        ts = datetime.fromisoformat(c["timestamp"]).strftime("%Y-%m-%d %H:%M")
        amount = c.get("amount", 0)
        total_rares += amount
        pool = c.get("pool", c.get("target", "?"))   # graceful fallback for old records
        vote = c.get("vote", "Any")
        lines.append(
            f"`#{c['id']}` **{c['player']}** — `{amount}` rares → Pool: **{pool}** banked by **{c['logged_by']}** at {ts}"
        )

    lines.append(f"\n**Total Rares in this list:** 💎 `{total_rares}`")

    content = "\n".join(lines)
    if len(content) > 2000:
        await interaction.response.send_message("⚠️ The list is too long to display in one message. Please use the `mine` filter.", ephemeral=True)
    else:
        await interaction.response.send_message(content)


@rares.command(name="leaderboard", description="Show who has contributed the most rares")
async def rare_contribution_leaderboard(interaction: discord.Interaction):
    contributions = load_contributions()
    if not contributions:
        await interaction.response.send_message("No contributions logged yet.")
        return

    totals = {}
    for c in contributions:
        totals[c["player"]] = totals.get(c["player"], 0) + c["amount"]

    sorted_totals = sorted(totals.items(), key=lambda x: x[1], reverse=True)

    lines = ["🏆 **Rare Contribution Leaderboard:**\n"]
    medals = ["🥇", "🥈", "🥉"]
    for i, (player, total) in enumerate(sorted_totals):
        prefix = medals[i] if i < 3 else f"`#{i+1}`"
        lines.append(f"{prefix} **{player}** — 💎 `{total}` rares")

    await interaction.response.send_message("\n".join(lines))


# ============================================================
# RARE LOST COMMAND
# ============================================================

@rares.command(name="lost", description="Log rares that were lost")
@app_commands.describe(
    amount="How many rares were lost",
    reason="Why the rares were lost"
)
async def rare_lost(interaction: discord.Interaction, amount: int, reason: str):
    user_roles = {r.name for r in interaction.user.roles}
    if not user_roles.intersection(moderator_roles):
        await interaction.response.send_message("❌ Only officers can log rare losses.", ephemeral=True)
        return

    if amount <= 0:
        await interaction.response.send_message("❌ Amount must be a positive number.", ephemeral=True)
        return

    lost = load_rare_lost()
    lost.append({
        "id": next_id(lost),
        "amount": amount,
        "reason": reason,
        "logged_by": interaction.user.name,
        "war": war,
        "timestamp": str(interaction.created_at)
    })
    save_rare_lost(lost)
    await interaction.response.send_message(
        f"📉 Logged loss of 💎 `{amount}` rares. Reason: *{reason}*"
    )


# ============================================================
# RARE BUILD COMMAND
# ============================================================

@rares.command(name="build", description="Log a vehicle that was built using rares")
@app_commands.describe(
    vehicle="The vehicle that was built",
    assigned_to="The member responsible for this vehicle (optional)"
)
@app_commands.autocomplete(vehicle=rare_cost_item_autocomplete)
@app_commands.autocomplete(assigned_to=guild_member_autocomplete)
async def rare_build(interaction: discord.Interaction, vehicle: str, assigned_to: str = None):
    user_roles = {r.name for r in interaction.user.roles}
    if not user_roles.intersection(moderator_roles):
        await interaction.response.send_message("❌ Only officers can log builds.", ephemeral=True)
        return

    match = next((item for item in RARE_COSTS if item["Name"].lower() == vehicle.lower()), None)
    if not match:
        await interaction.response.send_message(f"❌ `{vehicle}` was not found in the rare cost list.", ephemeral=True)
        return

    builds = load_rare_builds()
    build_id = next_id(builds)
    builds.append({
        "id": build_id,
        "vehicle": match["Name"],
        "rares_cost": match["Rares"],
        "assigned_to": assigned_to,
        "status": "alive",
        "logged_by": interaction.user.name,
        "war": war,
        "timestamp": str(interaction.created_at)
    })
    save_rare_builds(builds)

    assignee_note = f", assigned to **{assigned_to}**" if assigned_to else ""
    await interaction.response.send_message(
        f"🔨 Build logged: **{match['Name']}** (💎 `{match['Rares']}` rares spent){assignee_note} — ID: `{build_id}`"
    )

async def build_status_autocomplete(interaction: discord.Interaction, current: str):
    choices = ["alive", "dead"]
    return [app_commands.Choice(name=s, value=s) for s in choices if current.lower() in s.lower()]

# ============================================================
# RARE BUILD STATUS COMMAND
# ============================================================

@rares.command(name="build_status", description="Update the assigned member or status of a logged build")
@app_commands.describe(
    build_id="The ID of the build to update",
    status="Whether the vehicle is alive or dead",
    assigned_to="The member responsible for this vehicle"
)
@app_commands.autocomplete(status=build_status_autocomplete)
@app_commands.autocomplete(assigned_to=guild_member_autocomplete)
async def rare_build_status(interaction: discord.Interaction, build_id: int, status: str = None, assigned_to: str = None):
    user_roles = {r.name for r in interaction.user.roles}
    if not user_roles.intersection(moderator_roles):
        await interaction.response.send_message("❌ Only officers can update build status.", ephemeral=True)
        return

    if status is None and assigned_to is None:
        await interaction.response.send_message("❌ Provide at least a status or an assigned member to update.", ephemeral=True)
        return

    builds = load_rare_builds()
    match = next((b for b in builds if b["id"] == build_id), None)
    if not match:
        await interaction.response.send_message(f"❌ No build found with ID `{build_id}`.", ephemeral=True)
        return

    if status is not None:
        match["status"] = status
    if assigned_to is not None:
        match["assigned_to"] = assigned_to

    save_rare_builds(builds)

    changes = []
    if status is not None:
        changes.append(f"status → **{status}**")
    if assigned_to is not None:
        changes.append(f"assigned to → **{assigned_to}**")

    await interaction.response.send_message(
        f"✅ Build `#{build_id}` (**{match['vehicle']}**) updated: {', '.join(changes)}"
    )

# ============================================================
# RARE REPORT COMMAND
# ============================================================

@rares.command(name="report", description="Show pool progress towards goals, built vehicles, and losses")
async def rare_report(interaction: discord.Interaction):
    contributions = load_contributions()
    builds = load_rare_builds()
    lost = load_rare_lost()
    goals = load_goals()

    lines = ["📊 **Rare Contribution & Goal Report**\n"]

    # 1. First, calculate the "Pre-Loss" balance for every pool
    # We store this in a dict so we can manipulate it for the losses
    pool_data_map = {}
    for pool_name in POOL_CATEGORIES:
        # Gross Contributions
        pool_contribs = [c for c in contributions if c.get("pool") == pool_name]
        gross_total = sum(c["amount"] for c in pool_contribs)
        
        # Spent on builds
        cat_match = POOL_CATEGORIES[pool_name]
        if cat_match:
            spent = sum(b["rares_cost"] for b in builds if next((i["Category"] for i in RARE_COSTS if i["Name"] == b["vehicle"]), None) == cat_match)
        else:
            spent = sum(b["rares_cost"] for b in builds if next((i["Category"] for i in RARE_COSTS if i["Name"] == b["vehicle"]), None) not in ["Aircraft", "Ship"])
        
        pool_data_map[pool_name] = {
            "pre_loss_balance": gross_total - spent,
            "net_pool": gross_total - spent # We will subtract losses from this
        }

    # 2. Subtract Losses from the highest pools first
    remaining_loss_to_deduct = sum(l["amount"] for l in lost)
    
    # Sort pools by balance descending
    sorted_pools = sorted(pool_data_map.keys(), key=lambda x: pool_data_map[x]["pre_loss_balance"], reverse=True)

    for pool_name in sorted_pools:
        if remaining_loss_to_deduct <= 0:
            break
            
        current_pool_amt = pool_data_map[pool_name]["net_pool"]
        
        if current_pool_amt > 0:
            # Take either the whole loss or whatever is left in the pool
            deduction = min(current_pool_amt, remaining_loss_to_deduct)
            pool_data_map[pool_name]["net_pool"] -= deduction
            remaining_loss_to_deduct -= deduction

    # 3. Now generate the lines using the updated net_pool values
    for pool_name in POOL_CATEGORIES:
        net_pool = max(0, int(pool_data_map[pool_name]["net_pool"]))
        goal_data = goals.get(pool_name)
        
        if goal_data:
            item_name = goal_data["item"]
            cost = goal_data["cost"]
            percent = min(100, int((net_pool / cost) * 100)) if cost > 0 else 0
            bar = "🟦" * (percent // 10) + "⬜" * (10 - (percent // 10))
            
            lines.append(f"**{pool_name} Pool** — Target: **{item_name}**")
            lines.append(f"{bar} `{net_pool}/{cost}` ({percent}%)")
        else:
            lines.append(f"**{pool_name} Pool** — 💎 `{net_pool}` rares available (No active goal)")
        
        lines.append("")

    # ── Builds summary ─────────────────────────────────────────────────────────
    if builds:
        total_built_rares = sum(b["rares_cost"] for b in builds)
        lines.append(f"**Vehicles Built:** {len(builds)} total, consuming 💎 `{total_built_rares}` rares")
        for b in builds:
            ts          = datetime.fromisoformat(b["timestamp"]).strftime("%Y-%m-%d %H:%M")
            status_icon = "✅" if b.get("status", "alive") == "alive" else "💀"
            assignee    = f" — 👤 {b['assigned_to']}" if b.get("assigned_to") else ""
            lines.append(
                f"  {status_icon} `#{b['id']}` **{b['vehicle']}** — 💎 `{b['rares_cost']}` rares{assignee} (built {ts})"
            )
        lines.append("")

    # ── Losses summary ──
    grand_total_lost = sum(l["amount"] for l in lost)
    if lost:
        lines.append(f"**Rares Lost:** 💎 `{grand_total_lost}` rares across {len(lost)} event(s)")
        for l in lost:
            ts = datetime.fromisoformat(l["timestamp"]).strftime("%Y-%m-%d %H:%M")
            lines.append(f"  `#{l['id']}` `{l['amount']}` rares — *{l['reason']}* at {ts}")
        lines.append("")

# --- Grand Totals ---
    grand_total_contrib = sum(c["amount"] for c in contributions)
    grand_total_spent = sum(b["rares_cost"] for b in builds)
    remaining = grand_total_contrib - grand_total_spent - grand_total_lost
    
    lines.append(
        f"**Overall Ledger:** 💎 `{grand_total_contrib}` total | "
        f"`{grand_total_spent}` spent | "
        f"`{grand_total_lost}` lost | "
        f"`{remaining}` remaining"
    )

    await interaction.response.send_message("\n".join(lines))


tree.add_command(rares)


# ============================================================
# BANK MODULE
# Rare Bankers track their own physical stock of rares/alloys
# per storage location.
# ============================================================

bank = app_commands.Group(name="bank", description="Rare Banker personal accounting commands")

# ── Autocomplete helpers ─────────────────────────────────────────────────────

async def bank_location_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice]:
    """Suggest locations that already exist in any banker's account, plus 'loose'."""
    accounts = load_bank_accounts()
    seen: set[str] = {"loose"}
    for slots in accounts.values():
        seen.update(slots.keys())
    return [
        app_commands.Choice(name=loc, value=loc)
        for loc in sorted(seen)
        if current.lower() in loc.lower()
    ][:5]

async def bank_own_location_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice]:
    """Suggest locations the calling banker already has stock in."""
    accounts   = load_bank_accounts()
    banker     = interaction.user.name
    slots      = accounts.get(banker, {})
    candidates = sorted(slots.keys()) or ["loose"]
    return [
        app_commands.Choice(name=loc, value=loc)
        for loc in candidates
        if current.lower() in loc.lower()
    ][:5]

async def bank_spend_reason_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice]:
    """Suggest build targets from RARE_COSTS plus a free-text fallback."""
    choices = [
        app_commands.Choice(name=item["Name"], value=item["Name"])
        for item in RARE_COSTS
        if current.lower() in item["Name"].lower() and item.get("Alloys", 0) > 0
    ][:5]
    if current and not any(c.value.lower() == current.lower() for c in choices):
        choices.insert(0, app_commands.Choice(name=current, value=current))
    return choices[:5]

async def banker_member_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice]:
    """Suggest guild members who have the Rare Banker role using their username."""
    if not interaction.guild:
        return []
    
    results = []
    for member in interaction.guild.members:
        if member.bot:
            continue
        member_roles = {r.name for r in member.roles}
        if member_roles.intersection(banker_roles) and current.lower() in member.name.lower():
            # Show display name but return the actual username
            display = f"{member.display_name} (@{member.name})" if member.display_name != member.name else member.name
            results.append(app_commands.Choice(name=display, value=member.name))
    
    return results[:10]  # Increased slightly for better UX

# BANK HELP

@bank.command(name="help", description="List all bank commands and their functions")
async def bank_help(interaction: discord.Interaction):
    help_text = (
        "🏦 **Banking Commands Help**\n\n"
        "**View & Info**\n"
        "`/bank view` — Show all bankers' current stock (rares & alloys per location)\n"
        "`/bank log` — View recent bank transactions (with filters)\n\n"
        
        "**Transactions**\n"
        "`/bank deposit` — Deposit rares/alloys from your loose stock into a storage location\n"
        "`/bank cook` — Convert loose rares into alloys (20:1) and deposit to a location\n"
        "`/bank retrieve` — Move materials from a location back to your loose stock\n"
        "`/bank handover` — Transfer materials to another banker's loose stock\n"
        "`/bank spend` — Spend alloys from a location (e.g. building vehicles)\n"
        "`/bank lost` — Log rares/alloys that were lost or stolen from a location\n\n"
        
        "**Useful Tips:**\n"
        "• Only Rare Bankers can use these commands.\n"
        "• `loose` is your main portable stock.\n"
        "• Use `/bank cook` to convert rares → alloys at 20:1 before depositing.\n"
        "• Use `/bank log` with filters to see specific activity.\n"
    )

    embed = discord.Embed(
        title="Rare Bank System",
        description=help_text,
        color=discord.Color.blue()
    )
    embed.set_footer(text="Made by Darkenson")

    await interaction.response.send_message(embed=embed, ephemeral=True)

# ── /bank view ───────────────────────────────────────────────────────────────

@bank.command(name="view", description="Show all banker accounts — rares and alloys per location")
async def bank_view(interaction: discord.Interaction):
    user_roles = {r.name for r in interaction.user.roles}
    if not user_roles.intersection(banker_roles):
        await interaction.response.send_message("❌ Only Rare Bankers can view banker accounts.", ephemeral=True)
        return

    accounts = load_bank_accounts()
    # Filter to bankers who actually have something
    active = {b: slots for b, slots in accounts.items() if slots}

    if not active:
        await interaction.response.send_message("📭 No banker accounts have any stock yet.", ephemeral=True)
        return

    lines = ["🏦 **Banker Accounts**\n"]
    for banker, slots in sorted(active.items()):
        total_rares  = sum(s["rares"]  for s in slots.values())
        total_alloys = sum(s["alloys"] for s in slots.values())
        lines.append(f"**{banker}** — 💎 `{total_rares}` rares | 🪨 `{total_alloys}` alloys total")
        for loc, bal in sorted(slots.items()):
            if bal["rares"] > 0 or bal["alloys"] > 0:
                lines.append(f"  📦 **{loc}**: 💎 `{bal['rares']}` rares | 🪨 `{bal['alloys']}` alloys")
        lines.append("")

    await interaction.response.send_message("\n".join(lines))

# ── /bank deposit ────────────────────────────────────────────────────────────

@bank.command(name="deposit", description="Record rares/alloys deposited into a storage location")
@app_commands.describe(
    location="Where these materials are being stored",
    rares="Number of rares deposited (can be 0 if only alloys)",
    alloys="Number of alloys deposited (can be 0 if only rares)",
)
@app_commands.autocomplete(location=bank_location_autocomplete)
async def bank_deposit(interaction: discord.Interaction, location: str, rares: int = 0, alloys: int = 0):
    user_roles = {r.name for r in interaction.user.roles}
    if not user_roles.intersection(banker_roles):
        await interaction.response.send_message("❌ Only Rare Bankers can record deposits.", ephemeral=True)
        return

    if rares < 0 or alloys < 0:
        await interaction.response.send_message("❌ Values must be positive (≥ 0).", ephemeral=True)
        return
    if rares == 0 and alloys == 0:
        await interaction.response.send_message("❌ At least one of rares or alloys must be greater than 0.", ephemeral=True)
        return



    banker   = interaction.user.name
    accounts = load_bank_accounts()

    err = bank_debit(accounts, banker, "loose", rares, alloys)
    if err:
        await interaction.response.send_message(err, ephemeral=True)
        return

    bank_credit(accounts, banker, location, rares, alloys)
    save_bank_accounts(accounts)

    append_bank_log({
        "op":        "deposit",
        "banker":    banker,
        "location":  location,
        "rares":     rares,
        "alloys":    alloys,
        "timestamp": str(interaction.created_at),
    })

    await interaction.response.send_message(
        f"✅ Deposited to **{location}**: 💎 `{rares}` rares | 🪨 `{alloys}` alloys"
    )

# ── /bank retrieve ───────────────────────────────────────────────────────────

@bank.command(name="retrieve", description="Move rares/alloys out of a storage location back to loose")
@app_commands.describe(
    location="Where the materials are being retrieved from",
    rares="Number of rares to retrieve (can be 0 if only alloys)",
    alloys="Number of alloys to retrieve (can be 0 if only rares)",
)
@app_commands.autocomplete(location=bank_own_location_autocomplete)
async def bank_retrieve(interaction: discord.Interaction, location: str, rares: int = 0, alloys: int = 0):
    user_roles = {r.name for r in interaction.user.roles}
    if not user_roles.intersection(banker_roles):
        await interaction.response.send_message("❌ Only Rare Bankers can retrieve from accounts.", ephemeral=True)
        return

    if rares < 0 or alloys < 0:
        await interaction.response.send_message("❌ Values must be positive (≥ 0).", ephemeral=True)
        return
    if rares == 0 and alloys == 0:
        await interaction.response.send_message("❌ At least one of rares or alloys must be greater than 0.", ephemeral=True)
        return

    banker   = interaction.user.name
    accounts = load_bank_accounts()
    err      = bank_debit(accounts, banker, location, rares, alloys)
    if err:
        await interaction.response.send_message(err, ephemeral=True)
        return

    # Credit back to loose
    bank_credit(accounts, banker, "loose", rares, alloys)
    save_bank_accounts(accounts)

    append_bank_log({
        "op":        "retrieve",
        "banker":    banker,
        "location":  location,
        "rares":     rares,
        "alloys":    alloys,
        "timestamp": str(interaction.created_at),
    })

    await interaction.response.send_message(
        f"📤 Retrieved from **{location}** → loose: 💎 `{rares}` rares | 🪨 `{alloys}` alloys"
    )

# ── /bank handover ───────────────────────────────────────────────────────────

@bank.command(name="handover", description="Transfer rares/alloys from your account to another banker's loose stock")
@app_commands.describe(
    recipient="The banker receiving the materials (username)",
    location="The location you are retrieving from",
    rares="Number of rares to hand over (can be 0 if only alloys)",
    alloys="Number of alloys to hand over (can be 0 if only rares)",
)
@app_commands.autocomplete(recipient=banker_member_autocomplete)
@app_commands.autocomplete(location=bank_own_location_autocomplete)
async def bank_handover(interaction: discord.Interaction, recipient: str, location: str, rares: int = 0, alloys: int = 0):
    user_roles = {r.name for r in interaction.user.roles}
    if not user_roles.intersection(banker_roles):
        await interaction.response.send_message("❌ Only Rare Bankers can hand over stock.", ephemeral=True)
        return

    if rares < 0 or alloys < 0:
        await interaction.response.send_message("❌ Values must be positive (≥ 0).", ephemeral=True)
        return
    if rares == 0 and alloys == 0:
        await interaction.response.send_message("❌ At least one of rares or alloys must be greater than 0.", ephemeral=True)
        return

    banker = interaction.user.name

    if banker.lower() == recipient.lower():
        await interaction.response.send_message("❌ You can't hand over stock to yourself.", ephemeral=True)
        return

    # Optional: Verify recipient is actually a banker
    recipient_member = discord.utils.get(interaction.guild.members, name=recipient)
    if not recipient_member or not {r.name for r in recipient_member.roles}.intersection(banker_roles):
        await interaction.response.send_message("❌ Recipient is not a recognized Rare Banker.", ephemeral=True)
        return

    accounts = load_bank_accounts()
    err = bank_debit(accounts, banker, location, rares, alloys)
    if err:
        await interaction.response.send_message(err, ephemeral=True)
        return

    bank_credit(accounts, recipient, "loose", rares, alloys)
    save_bank_accounts(accounts)

    append_bank_log({
        "op":        "handover",
        "from":      banker,      # username
        "to":        recipient,   # now guaranteed to be username
        "location":  location,
        "rares":     rares,
        "alloys":    alloys,
        "timestamp": str(interaction.created_at),
    })

    await interaction.response.send_message(
        f"🤝 Handed over from **{location}** to **@{recipient}** (loose): 💎 `{rares}` rares | 🪨 `{alloys}` alloys"
    )

# ── /bank spend ──────────────────────────────────────────────────────────────

@bank.command(name="spend", description="Spend alloys from a storage location (e.g. to build a vehicle)")
@app_commands.describe(
    location="The storage location alloys are being spent from",
    alloys="Number of alloys to spend",
    reason="What the alloys were spent on",
)
@app_commands.autocomplete(location=bank_own_location_autocomplete)
@app_commands.autocomplete(reason=bank_spend_reason_autocomplete)
async def bank_spend(interaction: discord.Interaction, location: str, alloys: int, reason: str):
    user_roles = {r.name for r in interaction.user.roles}
    if not user_roles.intersection(banker_roles):
        await interaction.response.send_message("❌ Only Rare Bankers can log spending.", ephemeral=True)
        return

    if alloys <= 0:
        await interaction.response.send_message("❌ Alloy amount must be greater than 0.", ephemeral=True)
        return

    banker   = interaction.user.name
    accounts = load_bank_accounts()
    err      = bank_debit(accounts, banker, location, 0, alloys)
    if err:
        await interaction.response.send_message(err, ephemeral=True)
        return

    save_bank_accounts(accounts)

    append_bank_log({
        "op":        "spend",
        "banker":    banker,
        "location":  location,
        "alloys":    alloys,
        "reason":    reason,
        "timestamp": str(interaction.created_at),
    })

    await interaction.response.send_message(
        f"💸 Spent 🪨 `{alloys}` alloys from **{location}** — Reason: *{reason}*"
    )

# ── /bank lost ───────────────────────────────────────────────────────────────

@bank.command(name="lost", description="Log rares or alloys that were lost or stolen from a storage location")
@app_commands.describe(
    location="The location the materials were lost from",
    rares="Number of rares lost (can be 0 if only alloys)",
    alloys="Number of alloys lost (can be 0 if only rares)",
    reason="Why the materials were lost (e.g. 'stockpile was captured', 'stolen')",
)
@app_commands.autocomplete(location=bank_own_location_autocomplete)
async def bank_lost(interaction: discord.Interaction, location: str, reason: str, rares: int = 0, alloys: int = 0):
    user_roles = {r.name for r in interaction.user.roles}
    if not user_roles.intersection(banker_roles):
        await interaction.response.send_message("❌ Only Rare Bankers can log losses.", ephemeral=True)
        return

    if rares < 0 or alloys < 0:
        await interaction.response.send_message("❌ Values must be positive (≥ 0).", ephemeral=True)
        return
    if rares == 0 and alloys == 0:
        await interaction.response.send_message("❌ At least one of rares or alloys must be greater than 0.", ephemeral=True)
        return

    banker   = interaction.user.name
    accounts = load_bank_accounts()
    err      = bank_debit(accounts, banker, location, rares, alloys)
    if err:
        await interaction.response.send_message(err, ephemeral=True)
        return

    save_bank_accounts(accounts)

    append_bank_log({
        "op":       "lost",
        "banker":   banker,
        "location": location,
        "rares":    rares,
        "alloys":   alloys,
        "reason":   reason,
        "timestamp": str(interaction.created_at),
    })

    await interaction.response.send_message(
        f"📉 Lost from **{location}**: 💎 `{rares}` rares | 🪨 `{alloys}` alloys — Reason: *{reason}*"
    )

# ── /bank cook ───────────────────────────────────────────────────────────────

COOK_GIF_URL = "https://i.imgur.com/JjtIwMH.gif"

@bank.command(name="cook", description="Convert loose rares into alloys at 20:1 and deposit them to a location")
@app_commands.describe(
    location="The storage location to deposit the cooked alloys (and leftover rares) to",
    rares="Number of loose rares to cook (optional — defaults to all available loose rares)",
)
@app_commands.autocomplete(location=bank_location_autocomplete)
async def bank_cook(interaction: discord.Interaction, location: str, rares: int = None):
    user_roles = {r.name for r in interaction.user.roles}
    if not user_roles.intersection(banker_roles):
        await interaction.response.send_message("❌ Only Rare Bankers can cook.", ephemeral=True)
        return

    banker   = interaction.user.name
    accounts = load_bank_accounts()

    loose_rares  = accounts.get(banker, {}).get("loose", {}).get("rares", 0)
    loose_alloys = accounts.get(banker, {}).get("loose", {}).get("alloys", 0)

    if loose_rares == 0:
        await interaction.response.send_message("❌ You have no loose rares to cook.", ephemeral=True)
        return

    # Default to all loose rares if not specified
    rares_to_cook = loose_rares if rares is None else rares

    if rares_to_cook <= 0:
        await interaction.response.send_message("❌ Amount of rares to cook must be greater than 0.", ephemeral=True)
        return

    if rares_to_cook > loose_rares:
        await interaction.response.send_message(
            f"❌ Insufficient loose rares: have 💎 `{loose_rares}`, tried to cook `{rares_to_cook}`.",
            ephemeral=True
        )
        return

    cooked_alloys    = rares_to_cook // 20
    leftover_rares   = rares_to_cook % 20
    unconsumed_rares = loose_rares - rares_to_cook   # rares not touched at all

    if cooked_alloys == 0:
        await interaction.response.send_message(
            f"Not enough rares to make even 1 alloy — need at least 20, you're cooking `{rares_to_cook}`.",
            ephemeral=True
        )
        return

    # Debit all rares_to_cook from loose
    err = bank_debit(accounts, banker, "loose", rares_to_cook, 0)
    if err:
        await interaction.response.send_message(err, ephemeral=True)
        return

    # Credit leftover rares + cooked alloys to the target location
    bank_credit(accounts, banker, location, leftover_rares, cooked_alloys)
    save_bank_accounts(accounts)

    append_bank_log({
        "op":         "cook",
        "banker":     banker,
        "location":   location,
        "rares_in":   rares_to_cook,
        "alloys_out": cooked_alloys,
        "rares_left": leftover_rares,
        "timestamp":  str(interaction.created_at),
    })

    new_loose_rares = unconsumed_rares

    await interaction.response.send_message(
        f"🧪 **We've gotta cook, Mr. White!**\n"
        f"{COOK_GIF_URL}\n\n"
        f"**Starting loose balance:** 💎 `{loose_rares}` rares | 🪨 `{loose_alloys}` alloys\n\n"
        f"🔥 Cooked `{rares_to_cook}` rares → 🪨 `{cooked_alloys}` alloys "
        f"*(+💎 `{leftover_rares}` remainder)*\n\n"
        f"**Added at {location}:** 💎 `{leftover_rares}` rares | 🪨 `{cooked_alloys}` alloys\n"
        f"**Remaining loose:** 💎 `{new_loose_rares}` rares | 🪨 `{loose_alloys}` alloys" if location != "loose" else ""
    )

@bank.command(name="log", description="View recent bank transactions in a readable format")
@app_commands.describe(
    limit="How many recent entries to show (default 25, max 100)",
    banker="Filter by banker name (optional)",
    op="Filter by operation type: contribution_received, deposit, retrieve, handover, spend, cook, lost"
)
async def bank_log_cmd(interaction: discord.Interaction, limit: int = 25, banker: str = None, op: str = None):
    if not any(r.name in banker_roles for r in interaction.user.roles):
        await interaction.response.send_message("❌ Only Rare Bankers can view the bank log.", ephemeral=True)
        return

    if limit > 100:
        limit = 100
    if limit < 1:
        limit = 25

    log = load_bank_log()
    if not log:
        await interaction.response.send_message("📭 Bank log is empty.")
        return

    # Apply filters
    filtered = log
    if banker:
        filtered = [e for e in filtered if e.get("banker") == banker or e.get("from") == banker]
    if op:
        filtered = [e for e in filtered if e.get("op") == op]

    filtered = sorted(filtered, key=lambda x: x.get("log_id", 0), reverse=True)[:limit]

    if not filtered:
        await interaction.response.send_message("No entries match your filters.", ephemeral=True)
        return

    lines = ["**🏦 Bank Transaction Log**\n"]

    for entry in reversed(filtered):  # Show oldest → newest in the selected range
        ts = datetime.fromisoformat(entry["timestamp"].replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M")
        op = entry["op"]

        if op == "contribution_received":
            line = f"`#{entry['log_id']}` **{ts}** | **{entry['banker']}** received 💎 `{entry['rares']}` rares contribution from **{entry['from']}** "

        elif op == "deposit":
            line = f"`#{entry['log_id']}` **{ts}** | **{entry['banker']}** deposited to **{entry['location']}** — 💎 `{entry['rares']}` | 🪨 `{entry['alloys']}`"
            if entry.get("loose_consumed"):
                line += f" *(used {entry['loose_consumed']} loose rares)*"

        elif op == "retrieve":
            line = f"`#{entry['log_id']}` **{ts}** | **{entry['banker']}** retrieved from **{entry['location']}** — 💎 `{entry['rares']}` | 🪨 `{entry['alloys']}`"

        elif op == "handover":
            line = f"`#{entry['log_id']}` **{ts}** | **{entry['from']}** handed over to **{entry['to']}** from **{entry['location']}** — 💎 `{entry['rares']}` | 🪨 `{entry['alloys']}`"

        elif op == "spend":
            line = f"`#{entry['log_id']}` **{ts}** | **{entry['banker']}** spent 🪨 `{entry['alloys']}` alloys from **{entry['location']}** → *{entry['reason']}*"

        elif op == "cook":
            line = f"`#{entry['log_id']}` **{ts}** | **{entry['banker']}** cooked 💎 `{entry['rares_in']}` rares → 🪨 `{entry['alloys_out']}` alloys to **{entry['location']}** *(💎 `{entry['rares_left']}` leftover)*"

        elif op == "lost":
            line = f"`#{entry['log_id']}` **{ts}** | **{entry['banker']}** lost from **{entry['location']}** — 💎 `{entry['rares']}` rares | 🪨 `{entry['alloys']}` alloys → *{entry['reason']}*"

        else:
            line = f"`#{entry['log_id']}` **{ts}** | Unknown operation: {op}"

        lines.append(line)

    content = "\n".join(lines)

    if len(content) > 1950:  # Safety margin
        await interaction.response.send_message(
            f"📋 Showing last **{len(filtered)}** transactions (too many for one message).\n"
            f"Try a smaller `limit` or add filters.", ephemeral=True
        )
        return

    await interaction.response.send_message(content)

tree.add_command(bank)

@bot.event
async def on_ready():
    await tree.sync()  # Registers commands with Discord
    print(f"Logged in as {bot.user}. Commands synced.")
    print(f"Kill/loss info is saved in {KILLS_LOSSES_FILE}.")
    print(f"Rare costs have been read from {COSTS_FILE}.")
    set_config()
    print(f"Data is loaded and saved for regiment {regiment_tag}, war {war}, {shard} shard, on the {side} side.")
    init_roles()
    print(f"Moderator roles are assigned to the following roles: {moderator_roles}")

bot.run(os.environ["DISCORD_TOKEN"])