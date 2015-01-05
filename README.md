# Markdown Previewer

Watches a markdown file and displays a preview on localhost using GitHub's API.
Changes will automatically load via AJAX on every save.

## Usage
`./markdown_previewer.py MARKDOWNFILE_TO_WATCH.md`

By default, it will connect to a random port on localhost.
It will output the host and port it is connected to:

```Serving MARKDOWNFILE_TO_WATCH.md on HOST:PORT```

Go to HOST:PORT to preview the file.

## Rate limiting
The GitHub API has a rate limit of 60 requests an hour unless you authenticate.
Set the env variable `GITHUB_API_TOKEN` to a valid [GitHub API token](https://help.github.com/articles/creating-an-access-token-for-command-line-use/) to increase this limit substantially.
