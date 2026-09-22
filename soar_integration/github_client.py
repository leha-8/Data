"""
GitHub REST API Client for SOAR Incident Handling
Handles Issue creation, SOC assignment, workflow dispatching, and comment posting.
"""

import logging
from typing import Dict, Any, List, Optional
import httpx

from config import settings

logger = logging.getLogger("soar.github")


class GitHubClient:
    def __init__(
        self,
        token: Optional[str] = None,
        repository: Optional[str] = None
    ):
        self.token = token or settings.GITHUB_TOKEN
        self.repository = repository or settings.GITHUB_REPOSITORY
        self.base_url = "https://api.github.com"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "SOAR-Automation-Client/1.0"
        }

    def _ensure_configured(self):
        if not self.token:
            raise ValueError("GITHUB_TOKEN is missing or empty. Please set GITHUB_TOKEN in your environment or .env file.")
        if not self.repository or "/" not in self.repository:
            raise ValueError(f"Invalid GITHUB_REPOSITORY '{self.repository}'. Expected format 'owner/repo'.")

    async def create_incident_issue(
        self,
        title: str,
        body: str,
        labels: Optional[List[str]] = None,
        assignees: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Creates a new GitHub Issue for the security incident.
        Automatically retries without assignees if specified assignees are not collaborators.
        """
        self._ensure_configured()
        url = f"{self.base_url}/repos/{self.repository}/issues"

        payload: Dict[str, Any] = {
            "title": title,
            "body": body,
            "labels": labels or ["incident", "security", "soar-automated"]
        }

        target_assignees = assignees or settings.GITHUB_SOC_ASSIGNEES
        if target_assignees:
            payload["assignees"] = target_assignees

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, headers=self.headers, json=payload)

            # If assigning fails (e.g. user is not a collaborator on the repo), retry without assignees
            if response.status_code == 422 and "assignees" in payload:
                logger.warning(
                    f"Failed to create issue with assignees {target_assignees}. Retrying without assignees. "
                    f"Response: {response.text}"
                )
                payload.pop("assignees", None)
                response = await client.post(url, headers=self.headers, json=payload)

            if response.status_code not in (200, 201):
                error_msg = f"GitHub API error ({response.status_code}): {response.text}"
                logger.error(error_msg)
                raise RuntimeError(error_msg)

            issue_data = response.json()
            logger.info(
                f"Successfully created GitHub Incident Issue #{issue_data.get('number')}: {issue_data.get('html_url')}"
            )
            return issue_data

    async def trigger_workflow_dispatch(
        self,
        workflow_id: Optional[str] = None,
        ref: Optional[str] = None,
        inputs: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Triggers a GitHub Actions workflow using workflow_dispatch event.
        """
        self._ensure_configured()
        workflow = workflow_id or settings.GITHUB_WORKFLOW_FILE
        target_ref = ref or settings.GITHUB_WORKFLOW_REF
        url = f"{self.base_url}/repos/{self.repository}/actions/workflows/{workflow}/dispatches"

        payload = {
            "ref": target_ref,
            "inputs": inputs or {}
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, headers=self.headers, json=payload)

            if response.status_code == 204:
                logger.info(f"Triggered workflow '{workflow}' on ref '{target_ref}' with inputs: {inputs}")
                return True
            else:
                error_msg = f"Failed to trigger workflow dispatch ({response.status_code}): {response.text}"
                logger.error(error_msg)
                raise RuntimeError(error_msg)

    async def add_issue_comment(
        self,
        issue_number: int,
        comment: str
    ) -> Dict[str, Any]:
        """
        Posts a status update comment to an existing GitHub Issue.
        """
        self._ensure_configured()
        url = f"{self.base_url}/repos/{self.repository}/issues/{issue_number}/comments"

        payload = {"body": comment}

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, headers=self.headers, json=payload)
            if response.status_code not in (200, 201):
                logger.error(f"Failed to add comment to Issue #{issue_number}: {response.text}")
                return {}
            return response.json()


github_client = GitHubClient()
