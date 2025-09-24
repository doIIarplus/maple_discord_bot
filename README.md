# GPQ Bot

## Deploying and getting started.

### Requirements

I'm assuming that you're on a Unix environment. If not it should be fine, you will
just need to tweak some things.

You need some things installed:

1. Git; for downloading the code and deploying to Heroku. https://git-scm.com/
2. Heroku CLI; for deploying to Heroku and monitoring. https://devcenter.heroku.com/articles/heroku-cli
3. Python 3.10+; for running the code locally. https://www.python.org/downloads/

For the sake of brevity, I need to assume that you're familiar with Git. Google some guides if you're not.

### Discord Bot

https://discord.com/developers is where you manage the Discord bot. Unfortunately only one person can
"own" the bot, and you cannot transfer ownership. On the bright side you probably don't need
to touch this page often.

### Heroku

We use Heroku to serve the project. If you need to manage deployment you will need to get access
to the Heroku project. You can be added as a member to the project.

### Google Sheets

Access to the Google Sheets API is managed by a Service Account. This is configured using
a Google Account. You may need access to that Google Account.

### Downloading the code

1. Log into and set up GitHub.
2. Clone the repository. https://docs.github.com/en/repositories/creating-and-managing-repositories/cloning-a-repository

If you're doing this for the first time will probably want to read https://docs.github.com/en/authentication/connecting-to-github-with-ssh
since this is a private repository you need to prove that you have access to it.

### Running locally

The bot requires some secrets, all of which can be found on Heroku. Settings > Config Vars.
Locally, you can create a `.env` file in the root directory with the config vars.
Don't include the `PRODUCTION` config var!

For more information, see https://pypi.org/project/python-dotenv/#getting-started

To install all dependencies, run `pip install -r requirements.txt` from the root folder.
To run the bot locally, run `python src/main.py` from the root folder.

Keep in mind that this bot will conflict with the deployed bot. You may want to turn the production bot off during this time.

### Deploying

1. Push the code to github. `git push origin main`. https://docs.github.com/en/get-started/using-git/pushing-commits-to-a-remote-repository
2. The code will be auto deployed by Heroku.

If you want to manually deploy or you don't like this behaviour, you can configure it at: https://dashboard.heroku.com/apps/iced-gpq/deploy/github
