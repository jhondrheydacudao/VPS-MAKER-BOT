import random
import logging
import subprocess
import sys
import os
import re
import time
import concurrent.futures
import discord
from discord.ext import commands, tasks
import docker
import asyncio
from discord import app_commands

TOKEN = 'YOUR_DISCORD_BOT_TOKEN'  # Replace with your bot token
RAM_LIMIT = '1g'
SERVER_LIMIT = 12
database_file = 'database.txt'

intents = discord.Intents.default()
intents.messages = False
intents.message_content = False

bot = commands.Bot(command_prefix='/', intents=intents)
client = docker.from_env()

# Generate a random port for port forwarding
def generate_random_port():
    return random.randint(1025, 65535)

# Add instance details to the database
def add_to_database(user, container_name, ssh_command):
    with open(database_file, 'a') as f:
        f.write(f"{user}|{container_name}|{ssh_command}\n")

# Remove instance details from the database
def remove_from_database(ssh_command):
    if not os.path.exists(database_file):
        return
    with open(database_file, 'r') as f:
        lines = f.readlines()
    with open(database_file, 'w') as f:
        for line in lines:
            if ssh_command not in line:
                f.write(line)

# Get SSH command from the database
def get_ssh_command_from_database(container_id):
    if not os.path.exists(database_file):
        return None
    with open(database_file, 'r') as f:
        for line in f:
            if container_id in line:
                return line.split('|')[2]
    return None

# Get all servers for a user
def get_user_servers(user):
    if not os.path.exists(database_file):
        return []
    servers = []
    with open(database_file, 'r') as f:
        for line in f:
            if line.startswith(user):
                servers.append(line.strip())
    return servers

# Count the number of servers for a user
def count_user_servers(user):
    return len(get_user_servers(user))

# Get container ID from the database
def get_container_id_from_database(user, container_name):
    if not os.path.exists(database_file):
        return None
    with open(database_file, 'r') as f:
        for line in f:
            if line.startswith(user) and container_name in line:
                return line.split('|')[1]
    return None

# Bot event: When the bot is ready
@bot.event
async def on_ready():
    change_status.start()
    print(f'Bot is ready. Logged in as {bot.user}')
    await bot.tree.sync()

# Task: Update bot status with the number of active instances
@tasks.loop(seconds=5)
async def change_status():
    try:
        if os.path.exists(database_file):
            with open(database_file, 'r') as f:
                lines = f.readlines()
                instance_count = len(lines)
        else:
            instance_count = 0

        status = f"with {instance_count} Cloud Instances"
        await bot.change_presence(activity=discord.Game(name=status))
    except Exception as e:
        print(f"Failed to update status: {e}")

# Command: Deploy a new VPS/container
@bot.tree.command(name="deploy-ubuntu", description="Creates a new Instance with Ubuntu 22.04")
async def deploy_ubuntu(interaction: discord.Interaction):
    await create_server_task(interaction)

# Function: Create a new VPS/container and set up Serveo.net for SSH access
async def create_server_task(interaction: discord.Interaction):
    await interaction.response.send_message(embed=discord.Embed(description="Creating Instance, This takes a few seconds.", color=0x00ff00))
    user = str(interaction.user)
    if count_user_servers(user) >= SERVER_LIMIT:
        await interaction.followup.send(embed=discord.Embed(description="```Error: Instance Limit-reached```", color=0xff0000))
        return

    image = "ubuntu-22.04-with-tmate"  # Replace with your VPS image
    
    # Format the hostname as root@[Discord_username]
    discord_username = interaction.user.name  # Get the Discord username
    hostname = f"{discord_username}"  # Format the hostname

    try:
        # Start the VPS/container
        container_id = subprocess.check_output([
            "docker", "run", "-itd", "--privileged", "--cap-add=ALL", "--hostname", hostname, image
        ]).strip().decode('utf-8')
    except subprocess.CalledProcessError as e:
        await interaction.followup.send(embed=discord.Embed(description=f"Error creating Docker container: {e}", color=0xff0000))
        return

    try:
        # Use Serveo.net to forward SSH port (22) to a public IP and port
        serveo_process = await asyncio.create_subprocess_exec(
            "docker", "exec", container_id, "ssh", "-o", "StrictHostKeyChecking=no", "-R", "0:localhost:22", "serveo.net",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )

        # Capture Serveo.net output to get the public IP and port
        serveo_output = await serveo_process.stdout.readline()
        serveo_output = serveo_output.decode('utf-8').strip()
        if "Forwarding" in serveo_output:
            # Extract Serveo.net IP and port
            serveo_url = serveo_output.split(" ")[-1]
            serveo_ip, serveo_port = serveo_url.split(":")

            # Send the SSH command to the user via DM
            ssh_command = f"ssh root@{serveo_ip} -p {serveo_port}"
            await interaction.user.send(embed=discord.Embed(
                description=f"### Your VPS is ready!\n**SSH Command:** ```{ssh_command}```\n**Hostname:** {hostname}\n**OS:** Ubuntu 22.04",
                color=0x00ff00
            ))
            await interaction.followup.send(embed=discord.Embed(description="Instance created successfully. Check your DMs for SSH access details.", color=0x00ff00))

            # Add the instance to the database
            add_to_database(user, container_id, ssh_command)
        else:
            await interaction.followup.send(embed=discord.Embed(description="Failed to set up Serveo.net forwarding.", color=0xff0000))
            subprocess.run(["docker", "kill", container_id])
            subprocess.run(["docker", "rm", container_id])
    except Exception as e:
        await interaction.followup.send(embed=discord.Embed(description=f"Error setting up Serveo.net: {e}", color=0xff0000))
        subprocess.run(["docker", "kill", container_id])
        subprocess.run(["docker", "rm", container_id])

# Command: List all instances for a user
@bot.tree.command(name="list", description="Lists all your Instances")
async def list_servers(interaction: discord.Interaction):
    user = str(interaction.user)
    servers = get_user_servers(user)
    if servers:
        embed = discord.Embed(title="Your Instances", color=0x00ff00)
        for server in servers:
            _, container_name, _ = server.split('|')
            embed.add_field(name=container_name, value="Description: A server with 32GB RAM and 8 cores.", inline=False)
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message(embed=discord.Embed(description="You have no servers.", color=0xff0000))

# Command: Remove an instance
@bot.tree.command(name="remove", description="Removes an Instance")
@app_commands.describe(container_name="The name/ssh-command of your Instance")
async def remove_server(interaction: discord.Interaction, container_name: str):
    user = str(interaction.user)
    container_id = get_container_id_from_database(user, container_name)

    if not container_id:
        await interaction.response.send_message(embed=discord.Embed(description="No Instance found for your user with that name.", color=0xff0000))
        return

    try:
        subprocess.run(["docker", "stop", container_id], check=True)
        subprocess.run(["docker", "rm", container_id], check=True)
        
        remove_from_database(container_id)
        
        await interaction.response.send_message(embed=discord.Embed(description=f"Instance '{container_name}' removed successfully.", color=0x00ff00))
    except subprocess.CalledProcessError as e:
        await interaction.response.send_message(embed=discord.Embed(description=f"Error removing instance: {e}", color=0xff0000))

# Run the bot
bot.run(TOKEN)
