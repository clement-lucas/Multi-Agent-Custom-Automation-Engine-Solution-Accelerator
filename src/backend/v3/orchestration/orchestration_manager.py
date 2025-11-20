# Copyright (c) Microsoft. All rights reserved.
"""Orchestration manager to handle the orchestration logic."""
import asyncio
import logging
import uuid
from typing import List, Optional

from common.config.app_config import config
from common.database.database_factory import DatabaseFactory
from common.models.messages_kernel import TeamConfiguration
from semantic_kernel.agents.orchestration.magentic import MagenticOrchestration
from semantic_kernel.agents.runtime import InProcessRuntime

# Create custom execution settings to fix schema issues
from semantic_kernel.connectors.ai.open_ai import (
    AzureChatCompletion, OpenAIChatPromptExecutionSettings)
from semantic_kernel.contents import (ChatMessageContent,
                                      StreamingChatMessageContent)
from v3.callbacks.response_handlers import (agent_response_callback,
                                            streaming_agent_response_callback)
from v3.config.settings import connection_config, orchestration_config
from v3.magentic_agents.magentic_agent_factory import MagenticAgentFactory
from v3.models.messages import WebsocketMessageType
from v3.orchestration.human_approval_manager import HumanApprovalMagenticManager


class OrchestrationManager:
    """Manager for handling orchestration logic."""

    # Class-scoped logger (always available to classmethods)
    logger = logging.getLogger(f"{__name__}.OrchestrationManager")

    def __init__(self):
        self.user_id: Optional[str] = None
        # Optional alias (helps with autocomplete)
        self.logger = self.__class__.logger

    @classmethod
    async def init_orchestration(
        cls, agents: List, user_id: str = None
    ) -> MagenticOrchestration:
        """Main function to run the agents."""

        # Custom execution settings that should work with Azure OpenAI
        execution_settings = OpenAIChatPromptExecutionSettings(
            max_tokens=4000, temperature=0.1
        )

        credential = config.get_azure_credential(client_id=config.AZURE_CLIENT_ID)

        def get_token():
            token = credential.get_token("https://cognitiveservices.azure.com/.default")
            return token.token

        # 1. Create a Magentic orchestration with Azure OpenAI
        magentic_orchestration = MagenticOrchestration(
            members=agents,
            manager=HumanApprovalMagenticManager(
                user_id=user_id,
                chat_completion_service=AzureChatCompletion(
                    deployment_name=config.AZURE_OPENAI_DEPLOYMENT_NAME,
                    endpoint=config.AZURE_OPENAI_ENDPOINT,
                    ad_token_provider=get_token,  # Use token provider function
                ),
                execution_settings=execution_settings,
            ),
            agent_response_callback=cls._user_aware_agent_callback(user_id),
            streaming_agent_response_callback=cls._user_aware_streaming_callback(
                user_id
            ),
        )
        return magentic_orchestration

    @staticmethod
    def _user_aware_agent_callback(user_id: str):
        """Factory method that creates a callback with captured user_id"""

        def callback(message: ChatMessageContent):
            return agent_response_callback(message, user_id)

        return callback

    @staticmethod
    def _user_aware_streaming_callback(user_id: str):
        """Factory method that creates a streaming callback with captured user_id"""

        async def callback(
            streaming_message: StreamingChatMessageContent, is_final: bool
        ):
            return await streaming_agent_response_callback(
                streaming_message, is_final, user_id
            )

        return callback

    @classmethod
    async def get_current_or_new_orchestration(
        cls, user_id, team_config, team_switched: bool = False
    ):
        """get existing orchestration instance."""
        current_orchestration = orchestration_config.get_current_orchestration(user_id)
        
        if (
            current_orchestration is None or team_switched
        ):  # Only recreate on team switch, not on completion
            if current_orchestration is not None and team_switched:
                # Log why we're recreating
                cls.logger.info(f"Recreating orchestration for user {user_id}: team switched")
                
                for agent in current_orchestration._members:
                    if agent.name != "ProxyAgent":
                        try:
                            await agent.close()
                        except Exception as e:
                            cls.logger.error("Error closing agent: %s", e)
            factory = MagenticAgentFactory()
            agents = await factory.get_agents(user_id=user_id, team_config_input=team_config)
            orchestration_config.orchestrations[user_id] = await cls.init_orchestration(
                agents, user_id
            )
        return orchestration_config.get_current_orchestration(user_id)

    async def continue_orchestration(self, user_id, plan_id, input_task) -> None:
        """Continue an existing orchestration with a follow-up question, maintaining context."""
        
        self.logger.info(f"Continuing orchestration for user {user_id}, plan {plan_id}")
        
        # Get the team configuration for this user
        memory_store = await DatabaseFactory.get_database(user_id=user_id)
        user_current_team = await memory_store.get_current_team(user_id=user_id)
        team = await memory_store.get_team_by_id(
            team_id=user_current_team.team_id if user_current_team else None
        )
        
        if not team:
            raise ValueError(f"Team configuration not found for user {user_id}")
        
        # Get the existing orchestration (should exist and maintain context)
        magentic_orchestration = await self.get_current_or_new_orchestration(
            user_id=user_id,
            team_config=team,
            team_switched=False
        )
        
        if magentic_orchestration is None:
            raise ValueError("Orchestration not initialized for user.")
        
        # Set flag to indicate this is a continuation
        if hasattr(magentic_orchestration, "_manager"):
            magentic_orchestration._manager.is_continuation = True
            magentic_orchestration._manager.current_plan_id = plan_id
        
        try:
            if hasattr(magentic_orchestration, "_manager") and hasattr(
                magentic_orchestration._manager, "current_user_id"
            ):
                magentic_orchestration._manager.current_user_id = user_id
                self.logger.debug(f"DEBUG: Set user_id on manager = {user_id}")
        except Exception as e:
            self.logger.error(f"Error setting user_id on manager: {e}")
        
        runtime = InProcessRuntime()
        runtime.start()
        
        try:
            # Add follow-up question to conversation context
            follow_up_message = f"Follow-up question: {input_task.description}"
            
            orchestration_result = await magentic_orchestration.invoke(
                task=follow_up_message,
                runtime=runtime,
            )
            
            try:
                self.logger.info("\nProcessing follow-up question:")
                value = await orchestration_result.get()
                self.logger.info(f"\nFollow-up result:\n{value}")
                self.logger.info("=" * 50)
                
                # Send final result via WebSocket
                await connection_config.send_status_update_async(
                    {
                        "type": WebsocketMessageType.FINAL_RESULT_MESSAGE,
                        "data": {
                            "content": str(value),
                            "status": "completed",
                            "timestamp": asyncio.get_event_loop().time(),
                        },
                    },
                    user_id,
                    message_type=WebsocketMessageType.FINAL_RESULT_MESSAGE,
                )
                self.logger.info(f"Follow-up result sent via WebSocket to user {user_id}")
                
            except Exception as e:
                self.logger.info(f"Error: {e}")
                self.logger.info(f"Error type: {type(e).__name__}")
                if hasattr(e, "__dict__"):
                    self.logger.info(f"Error attributes: {e.__dict__}")
                self.logger.info("=" * 50)
        
        except Exception as e:
            self.logger.error(f"Unexpected error in continuation: {e}")
        finally:
            # Reset continuation flag
            if hasattr(magentic_orchestration, "_manager"):
                magentic_orchestration._manager.is_continuation = False
                magentic_orchestration._manager.current_plan_id = None
            await runtime.stop_when_idle()
    
    async def run_orchestration(self, user_id, input_task) -> None:
        """Run the orchestration with user input loop."""

        job_id = str(uuid.uuid4())

        # Use the new event-driven method to set approval as pending
        orchestration_config.set_approval_pending(job_id)

        # Get the team configuration for this user
        memory_store = await DatabaseFactory.get_database(user_id=user_id)
        user_current_team = await memory_store.get_current_team(user_id=user_id)
        team = await memory_store.get_team_by_id(team_id=user_current_team.team_id if user_current_team else None)
        
        if not team:
            raise ValueError(f"Team configuration not found for user {user_id}")
        
        # Get current or create new orchestration
        magentic_orchestration = await self.get_current_or_new_orchestration(
            user_id=user_id, 
            team_config=team, 
            team_switched=False
        )

        if magentic_orchestration is None:
            raise ValueError("Orchestration not initialized for user.")

        try:
            if hasattr(magentic_orchestration, "_manager") and hasattr(
                magentic_orchestration._manager, "current_user_id"
            ):
                magentic_orchestration._manager.current_user_id = user_id
                self.logger.debug(f"DEBUG: Set user_id on manager = {user_id}")
        except Exception as e:
            self.logger.error(f"Error setting user_id on manager: {e}")

        runtime = InProcessRuntime()
        runtime.start()

        try:

            orchestration_result = await magentic_orchestration.invoke(
                task=input_task.description,
                runtime=runtime,
            )

            try:
                self.logger.info("\nAgent responses:")
                value = await orchestration_result.get()
                self.logger.info(f"\nFinal result:\n{value}")
                self.logger.info("=" * 50)

                # Send final result via WebSocket
                await connection_config.send_status_update_async(
                    {
                        "type": WebsocketMessageType.FINAL_RESULT_MESSAGE,
                        "data": {
                            "content": str(value),
                            "status": "completed",
                            "timestamp": asyncio.get_event_loop().time(),
                        },
                    },
                    user_id,
                    message_type=WebsocketMessageType.FINAL_RESULT_MESSAGE,
                )
                self.logger.info(f"Final result sent via WebSocket to user {user_id}")
                    
            except Exception as e:
                self.logger.info(f"Error: {e}")
                self.logger.info(f"Error type: {type(e).__name__}")
                if hasattr(e, "__dict__"):
                    self.logger.info(f"Error attributes: {e.__dict__}")
                self.logger.info("=" * 50)

        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")
        finally:
            await runtime.stop_when_idle()
