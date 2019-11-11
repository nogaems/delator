# delator
Matrix bot

## Why this name?
Some folks on matrix are quite paranoid about their encrypted rooms logs might be leaked. So let's make them even more nervous.

## Commands:

### Already implemented:
* `%h` (help)
* `%echo`
* `%s` (search with DuckDuckGo)
* `%olm`

### Coming soon™:
* `%d` (dice)
* `%r` (remind)

## Features
* Encrypted rooms:
    * On join verifies manager accounts devices in joined rooms, blacklists everyone else (`%olm` command to manage users in room allowed only to a manager)
    * Preserves verified devices across restarts
* Automatically follows invites from manager accounts.
* Writes comprehensive logs (use `-l {DEBUG,INFO,WARNING,ERROR,CRITICAL}`).
* Easy-to-add command system: every correct python file within `commands` directory with a single coroutine `handler` inside will be treated as a valid command.
* Showing info about links being posted in rooms:
    * Title in case of an html-document link
    * MIME type for everything else
    * Indicator of unknown file type if it is complicated to guess what it is
    * Error message (usually if the link is invalid or something network-related happened)

# Deploy

## Preparation

```
cd
git clone https://github.com/nogaems/delator.git
cd delator
```
According to `config.py.example` file, fill up every field in `config.py`.

## Manual way

First off, we need to Install `olm` library (and its python binding), which is responsible of `e2e` encryption in matrix. As a Gentoo user, you might add `booboo` overlay and `emerge dev-libs/olm dev-python/python-olm` packages.
For any Debian-derivatives the `libolm` package doesn't seem to work properly (at the moment of writhing this guide), so you have to install it manally like that:
```
cd
git clone https://gitlab.matrix.org/matrix-org/olm.git
cd olm
make
sudo make install
ldconfig
cd python
sudo python setup.py install
```
Also make sure that you have `virtualenv` package installed.
Install all requirements in a virtual environment:
```
virtualenv --system-site-packages venv
source venv/bin/activate
pip install --user -r requirements.txt
```
After this getting done, you're ready to run your bot:
```
python main.py -l INFO
```
That's basically it.

## With Docker

```
mkdir ~/.delator
chmod -R a+w ~/.delator

docker build -t delator --build-arg NO_CACHE="`date`" .
docker run -v ~/.delator/:/home/user/delator/profile -it delator
```

# Add a command

In order to add your custom command to the bot, you have to create a python file within `commands` directory, let's say `my_command.py`.

```python
# my_command.py

# optional, if not set the name of this file will be used
name = 'command'

# optional
aliases = ('cmd', 'cmmnd')

# optional, will be shown on %help command
help = 'help string'

# mandatory
# note that this is a coroutine
# args will be a list of strings, the arguments passed to your command
# request is an instance of Request class defined here https://github.com/nogaems/delator/blob/master/command.py
async def handler(args, request):
    #do your things here
    await request.reply('response text')
```
There's nothing else you have to do, this is already a working command.

# Important!

* In order to preserve the last syncronization token and the list of devices that you've already verified, do **NOT** change your `store_path` configuration variable and do **NOT** delete the directory you've pointed out there. But if that happened, you have to change your `device_id` value and re-verify bot in your client. Otherwise, the bot won't be able to read messages in encrypted rooms.
* At startup it may take a while (usually about half a minute or so) for the bot to start serving your commands. That happens due to the large amount of http request to the homeserver. Have some patience, there's nothing to do about it.
* In order to prevent exposing services from your private networks, add these rules on the host you're running the bot at:
```
iptables -A FORWARD -i <interface> -s 10.0.0.0/8 -j DROP
iptables -A FORWARD -i <interface> -s 100.64.0.0/10 -j DROP
iptables -A FORWARD -i <interface> -s 172.16.0.0/12 -j DROP
iptables -A FORWARD -i <interface> -s 192.168.0.0/16 -j DROP
iptables -A FORWARD -i <interface> -s fc00::/7 -j DROP
```
