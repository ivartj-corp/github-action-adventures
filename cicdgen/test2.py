from cicdgen.github import GitHubCicdDriver
from fs.osfs import OSFS

driver = GitHubCicdDriver(fs=OSFS("/"))

foo = driver.getenv("foo")
assert foo == "bar"
