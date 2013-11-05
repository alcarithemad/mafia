import irc.bot
import irc.strings

import mafia

class MafiaBot(irc.bot.SingleServerIRCBot):
	def __init__(self, nickname, server, port=6667):
		irc.bot.SingleServerIRCBot.__init__(self, [(server, port)], nickname, nickname)
		self.name = nickname

	def on_nicknameinuse(self, c, e):
		c.nick(c.get_nickname() + "_")

	def on_welcome(self, c, e):
		print 'welcome'
		self.game = mafia.MafiaGame(self.connection, '')

	def on_privmsg(self, c, e):
		self.do_command(e, e.arguments)

	def on_pubmsg(self, c, e):
		a = e.arguments[0].split(":", 1)
		self.do_command(e, a)

	def do_command(self, e, a):
		cmd = a[0]
		print 'got msg', e, cmd
		nick = e.source.nick
		if e.target != self.name:
			dest = e.target
		else:
			dest = nick

		if cmd.startswith('!'):
			if cmd == '!help':
				self.game.help(nick)
			else:
				self.game.handle(e, dest, a)

def main():
	import sys

	s = sys.argv[1].split(":", 1)
	server = s[0]
	if len(s) == 2:
		try:
			port = int(s[1])
		except ValueError:
			print("Error: Erroneous port.")
			sys.exit(1)
	else:
		port = 6667

	bot = MafiaBot('Mafia', server, port)
	bot.start()

if __name__ == "__main__":
	main()