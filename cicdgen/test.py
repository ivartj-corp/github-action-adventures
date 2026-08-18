from cicdgen.github import GitHubCicdDriver
from fs.osfs import OSFS

driver = GitHubCicdDriver(fs=OSFS("/"))

driver.warning("warning")
driver.error("error")
driver.setenv("foo", "bar")
