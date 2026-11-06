"""Static security contracts for private-template CI access."""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = (ROOT / ".github/workflows/ci.yml",
             ROOT / ".github/workflows/docker-validation.yml")


class PrivateAccessWorkflows(unittest.TestCase):
    def test_workflows_keep_fork_runs_untrusted_and_permissions_minimal(self):
        for path in WORKFLOWS:
            with self.subTest(workflow=path.name):
                text = path.read_text(encoding="utf-8")
                self.assertNotIn("pull_request_target", text)
                lines = text.splitlines()
                permission_start = lines.index("permissions:")
                permission_block = []
                for line in lines[permission_start + 1:]:
                    if line and not line.startswith(" "):
                        break
                    permission_block.append(line)
                self.assertEqual(permission_block, ["  contents: read"])
                action_lines = re.findall(r"(?m)^\s*-\s*uses: .+$", text)
                self.assertTrue(action_lines)
                for line in action_lines:
                    self.assertRegex(line, r"@[0-9a-f]{40}(?:\s+#.*)?$")
                self.assertEqual(text.count("persist-credentials: false"),
                                 text.count("uses: actions/checkout@"))
                self.assertIn(
                    "if: github.event_name != 'push' || github.ref != 'refs/heads/main'", text
                )
                self.assertIn("Report template checks not verified for untrusted events", text)
                self.assertIn("run: python scripts/prepare_template_ci.py --untrusted", text)

    def test_secret_is_scoped_only_to_trusted_retrieval_steps(self):
        for path in WORKFLOWS:
            with self.subTest(workflow=path.name):
                lines = path.read_text(encoding="utf-8").splitlines()
                secret_lines = [
                    index for index, line in enumerate(lines)
                    if "secrets.T0003_READ_TOKEN" in line
                ]
                expected = 1 if path.name == "ci.yml" else 2
                self.assertEqual(len(secret_lines), expected)
                for index in secret_lines:
                    self.assertEqual(len(lines[index]) - len(lines[index].lstrip()), 10)
                    step_start = max(
                        i for i in range(index)
                        if re.match(r"^      - name:", lines[i])
                    )
                    step = "\n".join(lines[step_start:index + 1])
                    self.assertIn("Fetch pinned template refs (trusted push only)", step)
                    self.assertIn(
                        "if: github.event_name == 'push' && github.ref == 'refs/heads/main'", step
                    )
                    self.assertIn("GH_TOKEN: ${{ secrets.T0003_READ_TOKEN }}", step)
                self.assertNotRegex(
                    "\n".join(lines), r"(?m)^if:.*secrets\.|^  env:.*secrets\.|^    env:.*secrets\."
                )

    def test_template_dependent_jobs_run_only_after_successful_retrieval(self):
        ci = WORKFLOWS[0].read_text(encoding="utf-8")
        docker = WORKFLOWS[1].read_text(encoding="utf-8")
        gate = "if: steps.prepare_template.outputs.template_ready == 'true'"
        self.assertIn(gate, ci)
        self.assertIn(gate, docker)
        self.assertIn("run: python -m unittest discover -s integration -v", ci)
        self.assertIn("run: python scripts/docker_ci.py", docker)
        self.assertIn("run: python scripts/docker_ci.py --config-only", docker)

    def test_local_fixture_checks_are_not_secret_gated(self):
        ci = WORKFLOWS[0].read_text(encoding="utf-8")
        docker = WORKFLOWS[1].read_text(encoding="utf-8")
        self.assertIn(
            "- name: Generator and local fixture tests\n"
            "        run: python -m unittest discover -s tests -v", ci
        )
        self.assertIn(
            "- name: Docker and PostgreSQL validation (local fixture)\n"
            "        run: python tests/docker_fixture_ci.py", docker
        )
        self.assertIn(
            "- name: Docker configuration validation (local fixture)\n"
            "        run: python tests/docker_fixture_ci.py --config-only", docker
        )


if __name__ == "__main__":
    unittest.main()
