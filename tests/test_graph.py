from app.graph.workflow import create_investigation_graph, route_after_verification, create_initial_state


def test_graph_compilation():
    graph = create_investigation_graph()
    assert graph is not None


def test_route_after_verification_pass():
    state = create_initial_state({"id": "1", "service": "s"})
    state["verification_result"] = {"verified": True}
    state["investigation_status"] = "SUCCESS"

    next_node = route_after_verification(state)
    assert next_node == "__end__"


def test_route_after_verification_reinvestigate_loop():
    state = create_initial_state({"id": "1", "service": "s"}, max_iterations=2)
    state["verification_result"] = {"verified": False}
    state["investigation_status"] = "RUNNING"
    state["iteration_count"] = 1

    next_node = route_after_verification(state)
    assert next_node == "supervisor"


def test_route_after_verification_max_iteration_stop():
    state = create_initial_state({"id": "1", "service": "s"}, max_iterations=2)
    state["verification_result"] = {"verified": False}
    state["investigation_status"] = "INSUFFICIENT_EVIDENCE"
    state["iteration_count"] = 2

    next_node = route_after_verification(state)
    assert next_node == "__end__"
