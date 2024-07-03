from __future__ import annotations

import argparse
import asyncio
import os
import random
from datetime import datetime

from colorama import Back
from yaml import safe_load

from social_simulation.clock.clock import Clock
from social_simulation.social_agent.agents_generator import (
    generate_agents, generate_controllable_agents)
from social_simulation.social_platform.channel import Channel
from social_simulation.social_platform.platform import Platform
from social_simulation.social_platform.typing import ActionType

parser = argparse.ArgumentParser(description="Arguments for script.")
parser.add_argument(
    "--config_path",
    type=str,
    help="Path to the YAML config file.",
    required=False,
    default="",
)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
DEFAULT_DB_PATH = os.path.join(DATA_DIR, "mock_twitter.db")
DEFAULT_CSV_PATH = os.path.join(DATA_DIR, "user_all_id_time.csv")


async def running(
    db_path: str | None = DEFAULT_DB_PATH,
    csv_path: str | None = DEFAULT_CSV_PATH,
    num_timesteps: int = 3,
    clock_factor: int = 60,
    recsys_type: str = "twitter",
    controllable_user: bool = False,
) -> None:
    db_path = DEFAULT_DB_PATH if db_path is None else db_path
    csv_path = DEFAULT_CSV_PATH if csv_path is None else csv_path
    if os.path.exists(db_path):
        os.remove(db_path)

    start_time = datetime.now()
    clock = Clock(k=clock_factor)
    channel = Channel()
    infra = Platform(
        db_path,
        channel,
        clock,
        start_time,
        recsys_type=recsys_type,
    )
    task = asyncio.create_task(infra.running())
    if not controllable_user:
        agent_graph = await generate_agents(csv_path, channel)
    else:
        agent_graph, agent_user_id_mapping = await \
            generate_controllable_agents(channel, 1)
        agent_graph = await generate_agents(csv_path, channel, agent_graph,
                                            agent_user_id_mapping)
    start_hour = 1

    for timestep in range(num_timesteps):
        print(Back.GREEN + f"timestep:{timestep}" + Back.RESET)
        # 0.2 * timestep here means 1 timstep == 12 minutes
        simulation_time_hour = start_hour + 0.2 * timestep
        for node_id, node_data in agent_graph.get_agents():
            agent = node_data['agent']
            if agent.user_info.is_controllable is False:
                agent_ac_prob = random.random()
                threshold = agent.user_info.profile['other_info'][
                    'active_threshold'][int(simulation_time_hour % 24)]
                if agent_ac_prob < threshold:
                    await agent.perform_action_by_llm()
            else:
                await agent.perform_action_by_hci()

    await channel.write_to_receive_queue((None, None, ActionType.EXIT))
    await task


if __name__ == "__main__":
    args = parser.parse_args()
    if os.path.exists(args.config_path):
        with open(args.config_path, "r") as f:
            cfg = safe_load(f)
        data_params = cfg.get("data")
        simulation_params = cfg.get("simulation")
        asyncio.run(running(**data_params, **simulation_params))
    else:
        asyncio.run(running())
