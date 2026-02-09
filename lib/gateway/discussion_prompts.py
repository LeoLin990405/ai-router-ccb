"""Prompt builders for discussion workflows."""

from __future__ import annotations

from typing import List, Dict

from .models import DiscussionSession, DiscussionMessage


class DiscussionPromptBuilder:
    """Builds prompts for each round of discussion."""

    @staticmethod
    def build_proposal_prompt(topic: str, provider: str) -> str:
        """Build prompt for round 1 (proposal)."""
        return f"""You are participating in a multi-AI collaborative discussion.

**Topic**: {topic}

**Your Role**: Provide your initial proposal or analysis on this topic.

**Instructions**:
1. Analyze the topic thoroughly
2. Present your perspective, approach, or solution
3. Be specific and actionable
4. Consider potential challenges and trade-offs
5. Keep your response focused and well-structured

Please provide your proposal:"""

    @staticmethod
    def build_review_prompt(
        topic: str,
        provider: str,
        proposals: List[DiscussionMessage],
    ) -> str:
        """Build prompt for round 2 (review)."""
        proposals_text = ""
        for i, msg in enumerate(proposals, 1):
            proposals_text += f"\n### Proposal from {msg.provider}:\n{msg.content}\n"

        return f"""You are participating in a multi-AI collaborative discussion.

**Topic**: {topic}

**Your Role**: Review and provide feedback on the proposals from other AI participants.

**Other Proposals**:
{proposals_text}

**Instructions**:
1. Analyze each proposal's strengths and weaknesses
2. Identify areas of agreement and disagreement
3. Suggest improvements or alternatives
4. Point out any missing considerations
5. Be constructive and specific in your feedback

Please provide your review:"""

    @staticmethod
    def build_revision_prompt(
        topic: str,
        provider: str,
        original_proposal: DiscussionMessage,
        feedback: List[DiscussionMessage],
    ) -> str:
        """Build prompt for round 3 (revision)."""
        feedback_text = ""
        for msg in feedback:
            feedback_text += f"\n### Feedback from {msg.provider}:\n{msg.content}\n"

        return f"""You are participating in a multi-AI collaborative discussion.

**Topic**: {topic}

**Your Role**: Revise your original proposal based on the feedback received.

**Your Original Proposal**:
{original_proposal.content}

**Feedback Received**:
{feedback_text}

**Instructions**:
1. Consider all feedback carefully
2. Incorporate valid suggestions
3. Address concerns raised by others
4. Explain any changes you made
5. Present your revised proposal clearly

Please provide your revised proposal:"""

    @staticmethod
    def build_summary_prompt(
        session: DiscussionSession,
        all_messages: List[DiscussionMessage],
    ) -> str:
        """Build prompt for final summary."""
        # Group messages by round
        round_1 = [m for m in all_messages if m.round_number == 1]
        round_2 = [m for m in all_messages if m.round_number == 2]
        round_3 = [m for m in all_messages if m.round_number == 3]

        discussion_text = "## Round 1: Initial Proposals\n"
        for msg in round_1:
            discussion_text += f"\n### {msg.provider}:\n{msg.content}\n"

        if round_2:
            discussion_text += "\n## Round 2: Reviews and Feedback\n"
            for msg in round_2:
                discussion_text += f"\n### {msg.provider}:\n{msg.content}\n"

        if round_3:
            discussion_text += "\n## Round 3: Revised Proposals\n"
            for msg in round_3:
                discussion_text += f"\n### {msg.provider}:\n{msg.content}\n"

        return f"""You are the orchestrator of a multi-AI collaborative discussion.

**Topic**: {session.topic}

**Participants**: {', '.join(session.providers)}

**Full Discussion**:
{discussion_text}

**Your Task**: Synthesize the discussion and provide a comprehensive summary.

**Instructions**:
1. Identify key points of consensus among participants
2. Highlight areas of disagreement and different perspectives
3. Extract the most valuable insights and recommendations
4. Provide a clear, actionable conclusion
5. Note any unresolved questions or areas needing further exploration

Please provide your summary:"""
