import configparser
import subprocess
from urllib.parse import urlparse

import requests


class GithubBlame:
    def __init__(self, token):
        self.token = token

        if repository := get_github_repository():
            self.org, self.repository = repository
        else:
            self.org, self.repository = None, None

    def blame(self, filename, lineno):
        blame_output = get_blame_output(filename)

        hash_author_map = {}
        line_hash_map = {}

        current_hash = None

        for line in blame_output.split("\n"):
            parts = line.split()
            if not parts:
                continue

            if parts[0].isalnum() and len(parts[0]) == 40:
                current_hash = parts[0]
                line_hash_map[int(parts[1])] = current_hash

            elif parts[0] == "author-mail":
                hash_author_map[current_hash] = line.split(" ")[1].strip("<>")

        try:
            author = hash_author_map[line_hash_map[lineno]]
        except KeyError:
            return
        else:
            return {
                "email": author,
                "commit": line_hash_map[lineno],
                "github_username": self.get_github_user(author),
                "github_org": self.org,
                "github_repository": self.repository,
            }

    def get_github_user(self, email):
        url = f"https://api.github.com/search/commits?q=author-email:{email}"

        if self.org:
            url += f" org:{self.org}"
        if self.repository:
            url += f" repository:{self.repository}"

        headers = {"Authorization": f"token {self.token}"} if self.token else {}
        response = requests.get(url, headers=headers)
        data = response.json()

        try:
            if data["items"][0]["commit"]["author"]["email"] == email:
                return data["items"][0]["author"]["login"]
        except KeyError:
            return None


def get_blame_output(file):
    return subprocess.check_output(["git", "blame", file, "-p"]).decode("utf-8")


def get_github_repository():
    config = parse_git_config(".git/config")

    for section in config.sections():
        if section.replace("'", "").replace('"', "") == "remote origin":
            url = config[section].get("url")
            if not url:
                return None
            if "://" not in url:
                url = f"ssh://{url}"
            parsed = urlparse(url)
            repository = parsed.path.replace(".git", "").strip("/")
            try:
                org = parsed.netloc.split(":")[1]
            except IndexError:
                return None
            else:
                return org, repository


def parse_git_config(file_path):
    # Create a ConfigParser instance
    config = configparser.ConfigParser()

    # Read the .git/config file
    config.read(file_path)

    return config
