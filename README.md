# Description
Python package to collect some logs of my personal life.
# Installation
- Clone the repo
- Install requirements.txt: ```pip install requirements.txt```
- Create the file ```.env``` with your credentials, for example:
```aidl
aTimeLogger_user = your@emal.com
aTimeLogger_pass = your_password
```
# Usage
To create the database
```python -m logme init```

The file _config.ini_ should be created. For example in linux it is in _/home/<your_user>/.config/logme/config.ini_

Insert configuration for processing data. For example:

```aidl
[Sources]
src = aTimeLogger                                                                                                                                                                       
[LocalPaths]
storage = /home/<your_user>/logme_data
[aTimeLogger]
connection = api
days_to_retrieve_api = 7
```

To process data in your aTimeLogger account:
```aidl
python -m logme source aTimeLogger
```

# Sources
 - aTimeLogger app

# Notes

 The code base is the application [Build a Command-Line To-Do App With Python and Typer](https://realpython.com/python-typer-cli/) and the code is still full of useless for this project as you can see running

```aidl
python -m logme --help
```

<code><pre>
Usage: logme [OPTIONS] COMMAND [ARGS]...
Options:
  -v, --version         Show the application's version and exit.
  --install-completion  Install completion for the current shell.
  --show-completion     Show completion for the current shell, to copy it or
                        customize the installation.
  --help                Show this message and exit.

Commands:
  <del>add       Add a new to-do with a DESCRIPTION.</del>
  <del>clear     Remove all to-dos.</del>
  <del>complete  Complete a to-do by setting it as done using its TODO_ID.</del>
  init      Initialize the logme database.
  <del>list      List all to-dos.</del>
  <del>remove    Remove a to-do using its TODO_ID.</del>
  source    Process a source.
</pre></code>
