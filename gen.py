import discord
from discord import app_commands
from discord.ext import commands, tasks
import os
import random
import json
import logging
from datetime import datetime, timedelta
from typing import Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Constants
CONFIG_FILE = 'config.json'
ACCOUNTS_DB = 'accounts.json'
COOLDOWNS_DB = 'cooldowns.json'
STATS_DB = 'stats.json'

DEFAULT_CONFIG = {
    "token": "YOUR_BOT_TOKEN_HERE",
    "prefix": "!",
    "admin_roles": ["Admin"],
    "premium_roles": ["Premium"],
    "cooldown": {
        "free": 86400,  # 24 hours in seconds
        "premium": 3600  # 1 hour in seconds
    },
    "embed_color": 0x7289DA,
    "log_channel": None,
    "status_rotation": [
        "Generating accounts!",
        "Use /help for commands",
        "Premium accounts available!"
    ]
}

class AccountManager:
    @staticmethod
    def load_db(file_path, default={}):
        """Load JSON database file"""
        try:
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    return json.load(f)
            return default.copy()
        except Exception as e:
            logger.error(f"Failed to load {file_path}: {e}")
            return default.copy()

    @staticmethod
    def save_db(file_path, data):
        """Save data to JSON database file"""
        try:
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=4)
            return True
        except Exception as e:
            logger.error(f"Failed to save {file_path}: {e}")
            return False

    @staticmethod
    def get_accounts():
        """Load all accounts"""
        return AccountManager.load_db(ACCOUNTS_DB, {"free": {}, "premium": {}})

    @staticmethod
    def save_accounts(accounts):
        """Save all accounts"""
        return AccountManager.save_db(ACCOUNTS_DB, accounts)

    @staticmethod
    def get_cooldowns():
        """Load all cooldowns"""
        return AccountManager.load_db(COOLDOWNS_DB)

    @staticmethod
    def save_cooldowns(cooldowns):
        """Save all cooldowns"""
        return AccountManager.save_db(COOLDOWNS_DB, cooldowns)

    @staticmethod
    def get_stats():
        """Load statistics"""
        return AccountManager.load_db(STATS_DB, {
            "free_generated": 0,
            "premium_generated": 0,
            "accounts_added": 0
        })

    @staticmethod
    def save_stats(stats):
        """Save statistics"""
        return AccountManager.save_db(STATS_DB, stats)

    @staticmethod
    def add_account(account_type, service, credentials):
        """Add a new account to the database"""
        accounts = AccountManager.get_accounts()
        
        if service not in accounts[account_type]:
            accounts[account_type][service] = []
            
        accounts[account_type][service].append({
            "credentials": credentials,
            "used": False,
            "used_by": None,
            "used_at": None
        })
        
        if AccountManager.save_accounts(accounts):
            # Update stats
            stats = AccountManager.get_stats()
            stats["accounts_added"] += 1
            AccountManager.save_stats(stats)
            return True
        return False

    @staticmethod
    def get_random_account(account_type, service=None):
        """Get a random unused account"""
        accounts = AccountManager.get_accounts()
        
        if account_type not in accounts:
            return None
            
        if service:
            if service not in accounts[account_type]:
                return None
                
            available = [acc for acc in accounts[account_type][service] if not acc["used"]]
            if not available:
                return None
                
            account = random.choice(available)
            account["used"] = True
            account["used_at"] = datetime.now().isoformat()
            AccountManager.save_accounts(accounts)
            return account
            
        else:
            # Get all available accounts of the type
            available = []
            for serv, acc_list in accounts[account_type].items():
                available.extend([{**acc, "service": serv} for acc in acc_list if not acc["used"]])
                
            if not available:
                return None
                
            account = random.choice(available)
            # Mark as used
            accounts[account_type][account["service"]][
                accounts[account_type][account["service"]].index(account)
            ]["used"] = True
            accounts[account_type][account["service"]][
                accounts[account_type][account["service"]].index(account)
            ]["used_at"] = datetime.now().isoformat()
            AccountManager.save_accounts(accounts)
            return account

    @staticmethod
    def get_services(account_type):
        """Get list of services for an account type"""
        accounts = AccountManager.get_accounts()
        if account_type not in accounts:
            return []
            
        services = []
        for service, acc_list in accounts[account_type].items():
            if any(not acc["used"] for acc in acc_list):
                services.append(service)
                
        return services

    @staticmethod
    def get_stats_counts():
        """Get counts of available accounts"""
        accounts = AccountManager.get_accounts()
        stats = {
            "free": 0,
            "premium": 0,
            "services": {}
        }
        
        for acc_type in ["free", "premium"]:
            for service, acc_list in accounts[acc_type].items():
                available = sum(1 for acc in acc_list if not acc["used"])
                if available > 0:
                    if service not in stats["services"]:
                        stats["services"][service] = {"free": 0, "premium": 0}
                    stats["services"][service][acc_type] = available
                    stats[acc_type] += available
                    
        return stats

    @staticmethod
    def check_cooldown(user_id, account_type):
        """Check if user is on cooldown"""
        cooldowns = AccountManager.get_cooldowns()
        user_id = str(user_id)
        
        if user_id not in cooldowns:
            return None
            
        last_used = cooldowns[user_id].get(f"last_{account_type}")
        if not last_used:
            return None
            
        last_used = datetime.fromisoformat(last_used)
        cooldown_seconds = DEFAULT_CONFIG["cooldown"][account_type]
        remaining = (last_used + timedelta(seconds=cooldown_seconds)) - datetime.now()
        
        if remaining.total_seconds() > 0:
            return remaining
        return None

    @staticmethod
    def update_cooldown(user_id, account_type):
        """Update user's cooldown"""
        cooldowns = AccountManager.get_cooldowns()
        user_id = str(user_id)
        
        if user_id not in cooldowns:
            cooldowns[user_id] = {}
            
        cooldowns[user_id][f"last_{account_type}"] = datetime.now().isoformat()
        AccountManager.save_cooldowns(cooldowns)

    @staticmethod
    def update_stat(stat_type, increment=1):
        """Update statistics"""
        stats = AccountManager.get_stats()
        stats[stat_type] = stats.get(stat_type, 0) + increment
        AccountManager.save_stats(stats)

# Initialize config
config = AccountManager.load_db(CONFIG_FILE, DEFAULT_CONFIG)

# Initialize Discord bot with sharding
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.members = True

class MyBot(commands.AutoShardedBot):
    def __init__(self):
        super().__init__(
            command_prefix=commands.when_mentioned_or(config['prefix']),
            intents=intents,
            help_command=None
        )

    async def setup_hook(self):
        await self.tree.sync()

bot = MyBot()

# Background tasks
@tasks.loop(minutes=5)
async def rotate_status():
    """Rotate the bot's status message"""
    config = AccountManager.load_db(CONFIG_FILE, DEFAULT_CONFIG)
    if not config.get('status_rotation'):
        return
        
    current = getattr(rotate_status, 'current', -1) + 1
    if current >= len(config['status_rotation']):
        current = 0
    rotate_status.current = current
    
    status = config['status_rotation'][current]
    await bot.change_presence(activity=discord.Game(name=status))

@bot.event
async def on_ready():
    logger.info(f'Logged in as {bot.user} (ID: {bot.user.id})')
    logger.info(f'Connected to {len(bot.guilds)} guilds')
    logger.info(f'Running {bot.shard_count} shard(s)')
    
    # Start background tasks
    rotate_status.start()
    
    # Initial status
    config = AccountManager.load_db(CONFIG_FILE, DEFAULT_CONFIG)
    if config.get('status_rotation'):
        await bot.change_presence(activity=discord.Game(name=config['status_rotation'][0]))

# Command: Generate free account
@bot.hybrid_command(name="generate", description="Generate a free account")
@app_commands.describe(service="Specific service to get an account for")
async def generate(ctx: commands.Context, service: Optional[str] = None):
    """Generate a free account"""
    try:
        # Check cooldown
        cooldown = AccountManager.check_cooldown(ctx.author.id, "free")
        if cooldown:
            hours, remainder = divmod(int(cooldown.total_seconds()), 3600)
            minutes, seconds = divmod(remainder, 60)
            await ctx.send(
                f"You're on cooldown! Please wait {hours}h {minutes}m {seconds}s before generating another free account.",
                ephemeral=True
            )
            return
            
        # Get account
        account = AccountManager.get_random_account("free", service)
        if not account:
            await ctx.send(
                "Sorry, we're out of free accounts right now!" + 
                (f" (for {service})" if service else ""),
                ephemeral=True
            )
            return
            
        # Send account via DM
        try:
            embed = discord.Embed(
                title="Here's your free account!",
                description=f"```{account['credentials']}```",
                color=config['embed_color'],
                timestamp=datetime.now()
            )
            
            if service or 'service' in account:
                embed.set_footer(text=f"Service: {service or account['service']}")
                
            await ctx.author.send(embed=embed)
            await ctx.send("Check your DMs for your account!", ephemeral=True)
            
            # Update cooldown and stats
            AccountManager.update_cooldown(ctx.author.id, "free")
            AccountManager.update_stat("free_generated")
            
        except discord.Forbidden:
            await ctx.send("I couldn't DM you. Please enable DMs from server members!", ephemeral=True)
    except Exception as e:
        logger.error(f"Error in generate command: {e}", exc_info=True)
        await ctx.send("An error occurred while generating your account.", ephemeral=True)

# Command: Generate premium account
@bot.hybrid_command(name="premium", description="Generate a premium account")
@app_commands.describe(service="Specific service to get an account for")
async def premium(ctx: commands.Context, service: Optional[str] = None):
    """Generate a premium account"""
    try:
        config = AccountManager.load_db(CONFIG_FILE, DEFAULT_CONFIG)
        
        # Check if user has premium role
        has_premium = any(
            role.name in config['premium_roles'] 
            for role in ctx.author.roles
        )
        
        if not has_premium:
            await ctx.send(
                "You need a premium role to use this command!",
                ephemeral=True
            )
            return
            
        # Check cooldown
        cooldown = AccountManager.check_cooldown(ctx.author.id, "premium")
        if cooldown:
            hours, remainder = divmod(int(cooldown.total_seconds()), 3600)
            minutes, seconds = divmod(remainder, 60)
            await ctx.send(
                f"You're on cooldown! Please wait {hours}h {minutes}m {seconds}s before generating another premium account.",
                ephemeral=True
            )
            return
            
        # Get account
        account = AccountManager.get_random_account("premium", service)
        if not account:
            await ctx.send(
                "Sorry, we're out of premium accounts right now!" + 
                (f" (for {service})" if service else ""),
                ephemeral=True
            )
            return
            
        # Send account via DM
        try:
            embed = discord.Embed(
                title="Here's your premium account!",
                description=f"```{account['credentials']}```",
                color=0xF8C300,  # Gold color for premium
                timestamp=datetime.now()
            )
            
            if service or 'service' in account:
                embed.set_footer(text=f"Service: {service or account['service']}")
                
            await ctx.author.send(embed=embed)
            await ctx.send("Check your DMs for your premium account!", ephemeral=True)
            
            # Update cooldown and stats
            AccountManager.update_cooldown(ctx.author.id, "premium")
            AccountManager.update_stat("premium_generated")
            
        except discord.Forbidden:
            await ctx.send("I couldn't DM you. Please enable DMs from server members!", ephemeral=True)
    except Exception as e:
        logger.error(f"Error in premium command: {e}", exc_info=True)
        await ctx.send("An error occurred while generating your premium account.", ephemeral=True)

# Command: List available services
@bot.hybrid_command(name="services", description="List available services")
async def services(ctx: commands.Context):
    """List available services"""
    try:
        free_services = AccountManager.get_services("free")
        premium_services = AccountManager.get_services("premium")
        
        embed = discord.Embed(
            title="Available Services",
            color=config['embed_color'],
            timestamp=datetime.now()
        )
        
        if free_services:
            embed.add_field(
                name="Free Services",
                value="\n".join(f"• {s}" for s in free_services),
                inline=False
            )
        else:
            embed.add_field(
                name="Free Services",
                value="No free services available",
                inline=False
            )
            
        if premium_services:
            embed.add_field(
                name="Premium Services",
                value="\n".join(f"• {s}" for s in premium_services),
                inline=False
            )
        else:
            embed.add_field(
                name="Premium Services",
                value="No premium services available",
                inline=False
            )
            
        await ctx.send(embed=embed)
    except Exception as e:
        logger.error(f"Error in services command: {e}", exc_info=True)
        await ctx.send("An error occurred while fetching services.", ephemeral=True)

# Command: Show statistics
@bot.hybrid_command(name="stats", description="Show account statistics")
async def stats(ctx: commands.Context):
    """Show account statistics"""
    try:
        stats = AccountManager.get_stats_counts()
        total_stats = AccountManager.get_stats()
        
        embed = discord.Embed(
            title="Account Statistics",
            color=config['embed_color'],
            timestamp=datetime.now()
        )
        
        embed.add_field(
            name="Free Accounts",
            value=f"Available: {stats['free']}",
            inline=True
        )
        
        embed.add_field(
            name="Premium Accounts",
            value=f"Available: {stats['premium']}",
            inline=True
        )
        
        embed.add_field(
            name="Total Generated",
            value=f"Free: {total_stats['free_generated']}\nPremium: {total_stats['premium_generated']}",
            inline=False
        )
        
        # Add service breakdown if there are services
        if stats['services']:
            service_text = []
            for service, counts in stats['services'].items():
                service_text.append(
                    f"**{service}**: Free: {counts['free']}, Premium: {counts['premium']}"
                )
                
            embed.add_field(
                name="Services Breakdown",
                value="\n".join(service_text),
                inline=False
            )
            
        await ctx.send(embed=embed)
    except Exception as e:
        logger.error(f"Error in stats command: {e}", exc_info=True)
        await ctx.send("An error occurred while fetching statistics.", ephemeral=True)

# Command: Add accounts (Admin only)
@bot.hybrid_command(name="addaccounts", description="Add accounts to the database (Admin only)")
@app_commands.describe(
    account_type="Type of accounts (free/premium)",
    service="Service name",
    accounts="Text file with accounts (one per line)"
)
async def addaccounts(
    ctx: commands.Context,
    account_type: str,
    service: str,
    accounts: discord.Attachment
):
    """Add accounts to the database (Admin only)"""
    try:
        config = AccountManager.load_db(CONFIG_FILE, DEFAULT_CONFIG)
        
        # Check permissions
        if not any(role.name in config['admin_roles'] for role in ctx.author.roles):
            await ctx.send("You don't have permission to use this command.", ephemeral=True)
            return
            
        # Validate account type
        if account_type.lower() not in ("free", "premium"):
            await ctx.send("Account type must be either 'free' or 'premium'.", ephemeral=True)
            return
            
        # Check file type
        if not accounts.filename.endswith('.txt'):
            await ctx.send("Please upload a .txt file with one account per line.", ephemeral=True)
            return
            
        # Process file
        try:
            content = await accounts.read()
            accounts_list = content.decode('utf-8').splitlines()
            accounts_list = [acc.strip() for acc in accounts_list if acc.strip()]
            
            if not accounts_list:
                await ctx.send("The file doesn't contain any valid accounts.", ephemeral=True)
                return
                
            # Add to database
            added = 0
            for acc in accounts_list:
                if AccountManager.add_account(account_type.lower(), service, acc):
                    added += 1
                    
            if added > 0:
                await ctx.send(
                    f"Successfully added {added} {account_type} accounts for {service}!",
                    ephemeral=True
                )
            else:
                await ctx.send("Failed to add accounts to database.", ephemeral=True)
                
        except Exception as e:
            logger.error(f"Error processing accounts file: {e}", exc_info=True)
            await ctx.send("Failed to process the accounts file.", ephemeral=True)
    except Exception as e:
        logger.error(f"Error in addaccounts command: {e}", exc_info=True)
        await ctx.send("An error occurred while adding accounts.", ephemeral=True)

# Command: Help
@bot.hybrid_command(name="help", description="Show help information")
async def help_command(ctx: commands.Context):
    """Show help information"""
    try:
        config = AccountManager.load_db(CONFIG_FILE, DEFAULT_CONFIG)
        
        embed = discord.Embed(
            title="Account Generator Help",
            description="A bot that generates free and premium accounts for various services.",
            color=config['embed_color']
        )
        
        # General commands
        embed.add_field(
            name="General Commands",
            value=(
                "`/generate [service]` - Get a free account\n"
                "`/premium [service]` - Get a premium account (requires premium role)\n"
                "`/services` - List available services\n"
                "`/stats` - Show account statistics\n"
                "`/help` - Show this help message"
            ),
            inline=False
        )
        
        # Admin commands
        if any(role.name in config['admin_roles'] for role in ctx.author.roles):
            embed.add_field(
                name="Admin Commands",
                value=(
                    "`/addaccounts <type> <service> <file>` - Add accounts to the database\n"
                ),
                inline=False
            )
        
        embed.set_footer(text=f"Prefix: {config['prefix']}")
        await ctx.send(embed=embed)
    except Exception as e:
        logger.error(f"Error in help command: {e}", exc_info=True)
        await ctx.send("An error occurred while displaying help.", ephemeral=True)

if __name__ == '__main__':
    try:
        bot.run(config['token'])
    except Exception as e:
        logger.critical(f"Failed to start bot: {e}", exc_info=True)