"""
Tests for step-by-step execution hook.

Verifies that the StepByStepExecutionHook enables controlled node-by-node
execution through the interrupt mechanism.
"""

from unittest.mock import Mock, AsyncMock
import pytest
from strands.multiagent.graph import GraphBuilder
from strands.multiagent.base import Status, MultiAgentBase
from strands.agent.agent_result import AgentResult

from graph.interrupt_hook import StepByStepExecutionHook


class MockAgent(MultiAgentBase):
    """Mock agent that returns a simple result without making API calls."""

    def __init__(self, name: str):
        super().__init__()
        self.name = name
        self.call_count = 0

    async def invoke_async(self, task, invocation_state=None, **kwargs):
        """Mock invoke that returns a simple result."""
        self.call_count += 1
        # Create a mock result
        result = Mock(spec=AgentResult)
        result.status = Status.COMPLETED
        result.execution_time = 100
        result.accumulated_usage = {"inputTokens": 0, "outputTokens": 0, "totalTokens": 0}
        result.accumulated_metrics = {"latencyMs": 100}
        result.execution_count = 1
        result.interrupts = []
        result.__str__ = Mock(return_value=f"Result from {self.name}")
        result.agent_name = self.name
        return result

    async def stream_async(self, task, invocation_state=None, **kwargs):
        """Mock streaming that yields a simple result."""
        result = await self.invoke_async(task, invocation_state, **kwargs)
        yield {"result": result}


def test_first_node_executes_without_interrupt():
    """First node should execute without interruption."""
    # Create a simple 3-node graph with mock agents
    agent1 = MockAgent("agent1")
    agent2 = MockAgent("agent2")
    agent3 = MockAgent("agent3")

    builder = GraphBuilder()
    builder.add_node(agent1, "node1")
    builder.add_node(agent2, "node2")
    builder.add_node(agent3, "node3")
    builder.add_edge("node1", "node2")
    builder.add_edge("node2", "node3")
    builder.set_entry_point("node1")

    # Add the step-by-step hook
    hook = StepByStepExecutionHook()
    builder.set_hook_providers([hook])

    graph = builder.build()

    # Execute the graph
    result = graph("test task")

    # Should interrupt before second node
    assert result.status == Status.INTERRUPTED
    assert result.completed_nodes == 1  # Only first node completed
    assert len(result.interrupts) == 1
    assert result.interrupts[0].name == "step_by_step_execution"
    assert "node2" in result.interrupts[0].reason

    # Verify only agent1 was called
    assert agent1.call_count == 1
    assert agent2.call_count == 0
    assert agent3.call_count == 0


def test_resume_executes_next_node():
    """After resume, the next node should execute and interrupt again."""
    # Create a simple 3-node graph
    agent1 = MockAgent("agent1")
    agent2 = MockAgent("agent2")
    agent3 = MockAgent("agent3")

    builder = GraphBuilder()
    builder.add_node(agent1, "node1")
    builder.add_node(agent2, "node2")
    builder.add_node(agent3, "node3")
    builder.add_edge("node1", "node2")
    builder.add_edge("node2", "node3")
    builder.set_entry_point("node1")

    # Add the step-by-step hook
    hook = StepByStepExecutionHook()
    builder.set_hook_providers([hook])

    graph = builder.build()

    # First invocation - should execute node1 and interrupt
    result1 = graph("test task")
    assert result1.status == Status.INTERRUPTED
    assert result1.completed_nodes == 1

    # Resume - should execute node2 and interrupt again
    interrupt_id = result1.interrupts[0].id
    resume_input = [{"interruptResponse": {"interruptId": interrupt_id, "response": "continue"}}]
    result2 = graph(resume_input)

    assert result2.status == Status.INTERRUPTED
    assert result2.completed_nodes == 2  # node1 and node2 completed
    assert len(result2.interrupts) == 1
    assert result2.interrupts[0].name == "step_by_step_execution"
    assert "node3" in result2.interrupts[0].reason

    # Verify agent1 and agent2 were called, but not agent3
    assert agent1.call_count == 1
    assert agent2.call_count == 1
    assert agent3.call_count == 0


def test_final_node_completes_without_interrupt():
    """The final node should complete without additional interrupts."""
    # Create a simple 3-node graph
    agent1 = MockAgent("agent1")
    agent2 = MockAgent("agent2")
    agent3 = MockAgent("agent3")

    builder = GraphBuilder()
    builder.add_node(agent1, "node1")
    builder.add_node(agent2, "node2")
    builder.add_node(agent3, "node3")
    builder.add_edge("node1", "node2")
    builder.add_edge("node2", "node3")
    builder.set_entry_point("node1")

    # Add the step-by-step hook
    hook = StepByStepExecutionHook()
    builder.set_hook_providers([hook])

    graph = builder.build()

    # First invocation - execute node1
    result1 = graph("test task")
    assert result1.status == Status.INTERRUPTED

    # Second invocation - execute node2
    interrupt_id1 = result1.interrupts[0].id
    resume_input1 = [{"interruptResponse": {"interruptId": interrupt_id1, "response": "continue"}}]
    result2 = graph(resume_input1)
    assert result2.status == Status.INTERRUPTED

    # Third invocation - execute node3 (final node)
    interrupt_id2 = result2.interrupts[0].id
    resume_input2 = [{"interruptResponse": {"interruptId": interrupt_id2, "response": "continue"}}]
    result3 = graph(resume_input2)

    # Should complete without interruption
    assert result3.status == Status.COMPLETED
    assert result3.completed_nodes == 3  # All nodes completed
    assert len(result3.interrupts) == 0  # No new interrupts

    # Verify all agents were called
    assert agent1.call_count == 1
    assert agent2.call_count == 1
    assert agent3.call_count == 1


def test_hook_counter_resets_on_resume():
    """The hook's execution counter should reset on each resume."""
    # Create a simple 2-node graph
    agent1 = MockAgent("agent1")
    agent2 = MockAgent("agent2")

    builder = GraphBuilder()
    builder.add_node(agent1, "node1")
    builder.add_node(agent2, "node2")
    builder.add_edge("node1", "node2")
    builder.set_entry_point("node1")

    # Add the step-by-step hook
    hook = StepByStepExecutionHook()
    builder.set_hook_providers([hook])

    graph = builder.build()

    # First invocation
    result1 = graph("test task")
    assert result1.status == Status.INTERRUPTED
    assert result1.completed_nodes == 1

    # Verify the hook's counter is reset (by checking that resume works)
    interrupt_id = result1.interrupts[0].id
    resume_input = [{"interruptResponse": {"interruptId": interrupt_id, "response": "continue"}}]
    result2 = graph(resume_input)

    # Should complete (only 2 nodes total)
    assert result2.status == Status.COMPLETED
    assert result2.completed_nodes == 2


def test_single_node_graph_completes_immediately():
    """A single-node graph should complete without any interrupts."""
    agent1 = MockAgent("agent1")

    builder = GraphBuilder()
    builder.add_node(agent1, "node1")
    builder.set_entry_point("node1")

    # Add the step-by-step hook
    hook = StepByStepExecutionHook()
    builder.set_hook_providers([hook])

    graph = builder.build()

    # Execute - should complete immediately since there's only one node
    result = graph("test task")

    assert result.status == Status.COMPLETED
    assert result.completed_nodes == 1
    assert len(result.interrupts) == 0
    assert agent1.call_count == 1


def test_parallel_entry_points_interrupt_correctly():
    """
    With parallel entry points, the hook interrupts before the second node in the batch.
    This ensures true step-by-step execution (one node at a time), even for parallel nodes.
    """
    # Create a graph with 2 parallel entry points, then a join node
    agent1 = MockAgent("agent1")
    agent2 = MockAgent("agent2")
    agent3 = MockAgent("agent3")

    builder = GraphBuilder()
    builder.add_node(agent1, "node1")
    builder.add_node(agent2, "node2")
    builder.add_node(agent3, "node3")
    builder.set_entry_point("node1")
    builder.set_entry_point("node2")
    builder.add_edge("node1", "node3")
    builder.add_edge("node2", "node3")

    # Add the step-by-step hook
    hook = StepByStepExecutionHook()
    builder.set_hook_providers([hook])

    graph = builder.build()

    # First invocation - executes first node and interrupts before the second
    result1 = graph("test task")

    assert result1.status == Status.INTERRUPTED
    assert result1.completed_nodes == 1  # Only one node completed
    assert len(result1.interrupts) == 1
    assert result1.interrupts[0].name == "step_by_step_execution"

    # Only one node should have been called (either node1 or node2, depending on execution order)
    assert (agent1.call_count == 1 and agent2.call_count == 0) or (agent1.call_count == 0 and agent2.call_count == 1)

    # Resume - execute the second entry point
    interrupt_id1 = result1.interrupts[0].id
    resume_input1 = [{"interruptResponse": {"interruptId": interrupt_id1, "response": "continue"}}]
    result2 = graph(resume_input1)

    # Should interrupt again before node3
    assert result2.status == Status.INTERRUPTED
    assert result2.completed_nodes == 2  # Both entry points completed

    # Both entry points should now have been called
    assert agent1.call_count == 1
    assert agent2.call_count == 1
    assert agent3.call_count == 0

    # Resume - execute node3 and complete
    interrupt_id2 = result2.interrupts[0].id
    resume_input2 = [{"interruptResponse": {"interruptId": interrupt_id2, "response": "continue"}}]
    result3 = graph(resume_input2)

    assert result3.status == Status.COMPLETED
    assert result3.completed_nodes == 3
    assert agent3.call_count == 1
