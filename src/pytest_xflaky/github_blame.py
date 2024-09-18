import subprocess
import sys

import requests


class GithubBlame:
    def __init__(self, token):
        self.token = token

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
                line_hash_map[int(parts[2])] = current_hash

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
            }

    def get_github_user(self, email):
        url = f"https://api.github.com/search/commits?q=author-email:{email}"

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


if __name__ == "__main__":
    blame = GithubBlame(None)
    print(blame.blame(sys.argv[1], int(sys.argv[2])))
