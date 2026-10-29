"""Check a container started with its default JupyterLab command."""

import json
from pathlib import Path
import socket
from time import monotonic, sleep
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

from jupyter_client import BlockingKernelClient
from jupyter_core.paths import jupyter_runtime_dir
from jupyter_server.serverapp import list_running_servers


def main() -> None:
    # Use the container's network interface, as a published Docker port would,
    # so binding the server only to loopback cannot pass this check.
    base_url = f"http://{socket.gethostbyname(socket.gethostname())}:8888"
    opener = build_opener(ProxyHandler({}))
    deadline = monotonic() + 60
    token = None
    while monotonic() < deadline:
        servers = list(list_running_servers())
        if servers:
            token = servers[0]["token"]
            try:
                request = Request(
                    f"{base_url}/api/status",
                    headers={"Authorization": f"token {token}"},
                )
                with opener.open(request, timeout=2) as response:
                    if response.status == 200:
                        break
            except (URLError, TimeoutError):
                pass
        sleep(0.5)
    else:
        raise AssertionError("JupyterLab did not become ready on port 8888")

    assert token, "JupyterLab must generate an authentication token"
    try:
        opener.open(f"{base_url}/api/kernels", timeout=5).close()
    except HTTPError as error:
        assert error.code == 403, f"Unexpected unauthenticated status: {error.code}"
    else:
        raise AssertionError("The kernel API allowed unauthenticated access")

    def api(path, method="GET", document=None):
        data = None if document is None else json.dumps(document).encode()
        request = Request(
            f"{base_url}{path}", data=data, method=method,
            headers={
                "Authorization": f"token {token}",
                "Content-Type": "application/json",
            },
        )
        return opener.open(request, timeout=15)

    with api("/lab") as response:
        assert b"JupyterLab" in response.read(), "JupyterLab page is missing"
    with api("/api/kernels", "POST", {"name": "python3"}) as response:
        kernel_id = json.load(response)["id"]

    client = BlockingKernelClient(
        connection_file=str(Path(jupyter_runtime_dir()) / f"kernel-{kernel_id}.json"),
    )
    try:
        client.load_connection_file()
        client.start_channels()
        client.wait_for_ready(timeout=30)
        reply = client.execute_interactive(
            "from pathlib import Path\n"
            "from tempfile import TemporaryDirectory\n"
            "from mocha import TransitionSystem, check_invariant\n"
            "from mocha.visualisation import to_graphviz\n"
            "system = TransitionSystem.from_components(\n"
            "    states={'q'}, actions={'tick'},\n"
            "    transitions={('q', 'tick', 'q')}, initial_states={'q'},\n"
            ")\n"
            "assert check_invariant(system, {'q'}).satisfies\n"
            "assert b'<svg' in to_graphviz(system).pipe(format='svg')\n"
            "with TemporaryDirectory(dir='/work') as directory:\n"
            "    path = Path(directory) / 'notebook-output.txt'\n"
            "    path.write_text('MoChA notebook kernel works')\n"
            "    assert path.read_text() == 'MoChA notebook kernel works'\n",
            timeout=30,
        )
        assert reply["content"]["status"] == "ok", reply["content"]
    finally:
        client.stop_channels()
        with api(f"/api/kernels/{kernel_id}", "DELETE"):
            pass

    print("JupyterLab smoke test passed: authentication, kernel, MoChA, SVG, and files.")


if __name__ == "__main__":
    main()
