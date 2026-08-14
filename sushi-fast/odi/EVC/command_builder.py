from __future__ import annotations

from uuid import uuid4

from .clip_pool import find_action_clip, find_core_clip
from .schema import (
    AudienceRuntimeState,
    BehaviorChoice,
    ClipPoolCatalog,
    SegmentContext,
    UnityCommand,
)


START_OFFSETS = {
    "during_speech": 0.10,
    "utterance_boundary": 0.05,
    "silence_or_pause": 0.10,
    "slide_transition": 0.05,
}


def build_unity_commands(
    *,
    agent: AudienceRuntimeState,
    core: BehaviorChoice | None,
    action: BehaviorChoice | None,
    catalog: ClipPoolCatalog,
    context: SegmentContext,
    accepted_time_s: float,
) -> list[UnityCommand]:
    start_time = accepted_time_s + START_OFFSETS[context.utterance_position]
    commands: list[UnityCommand] = []
    if core is not None:
        clip = find_core_clip(catalog, core.variation_id)
        commands.extend(
            _commands_for_mapping(
                agent=agent,
                choice=core,
                mappings=clip.unity_actions,
                start_time=start_time,
                priority=50,
            )
        )
    if action is not None:
        clip = find_action_clip(catalog, action.variation_id)
        commands.extend(
            _commands_for_mapping(
                agent=agent,
                choice=action,
                mappings=clip.unity_actions,
                start_time=start_time,
                priority=100,
            )
        )
    return commands


def _commands_for_mapping(
    *,
    agent: AudienceRuntimeState,
    choice: BehaviorChoice,
    mappings,
    start_time: float,
    priority: int,
) -> list[UnityCommand]:
    sync_group = uuid4()
    return [
        UnityCommand(
            agent_id=agent.agent_id,
            start_time=start_time,
            layer=mapping.layer,
            action_id=mapping.action_id,
            duration=mapping.duration,
            sync_group=sync_group,
            selected_behavior_id=choice.behavior_id,
            selected_variation_id=choice.variation_id,
            priority=priority,
            blend_mode=mapping.blend_mode,
            intensity=agent.profile.expressivity,
        )
        for mapping in mappings
    ]


def commit_command_times(agent: AudienceRuntimeState, commands: list[UnityCommand]) -> None:
    body_times = [command.start_time for command in commands if command.layer == "Body"]
    if body_times:
        agent.last_body_command_time = max(body_times)
