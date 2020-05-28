import sys
import glob
import re
import os

dirs = sys.argv[1:]

smalis = [] # All the smalis in path

TAG = 'smalter'

for _dir in dirs:
	for root, dirs, files in os.walk(_dir):
		smalis += glob.glob(root + '/*.smali')

print '%d smalis found...' % len(smalis) 
print

for smali in smalis:
	_class = None
	source = None

	methods = []

	method = None
	registers = 0
	params = []

	f = open(smali, 'r+b')
	for line in f:
		line = line.strip()

		if '.class' in line:
			match = re.search('^\.class.*(L.*;)$', line)
			if match:
				_class = match.group(1)

		if '.source' in line:
			match = re.search('^\.source.*"(.*).(java|kt)"$', line)
			if match:
				source = match.group(1)

		if line.startswith('.method'):
			method = None
			registers = 0
			params = []
			signature = line

			# Grab the number of parameters
			match = re.search(' (\S+)\((.*)\)', line)
			if match:
				method = match.group(1)
				params = re.findall('(\[*(?:[VZBVSCIJFD]|L.*?;))', match.group(2))

		if '.registers' in line:
			(_, registers) = line.split(' ')
			registers = int(registers, 10)

		if line.startswith('.end method'):
			if method:
				methods.append((method, signature, params, registers))

	f.seek(0)
	code = f.read()

	for method, signature, params, registers in methods:
		if ' abstract ' in signature:
			continue

		if ' synthetic ' in signature:
			continue

		if ' bridge ' in signature:
			continue

		ps = len(params)
		if ' static ' not in signature:
			ps += 1 # Non static methods will have p0 as 'this'

		if ps + 3 > 16:
			# There's a limit to offsetting parameters by too much, static calls are done with 4-bit register references
			print 'Skipping %s.%s(%s) in %s, too many parameters (16 max)' % (_class, method, ''.join(params), smali)
			continue

		# Find the registers line
		match = re.findall(r'^%s.*?\.end method$' % re.escape(signature), code, re.DOTALL | re.MULTILINE)
		if len(match) > 1:
			print 'More than one method found with signature in %s: %s' % (smali, signature)
			continue
		elif not match:
			print '%s not found in %s' % (signature, smali)
			continue

		original = match.pop()
		replace  = original

		# Make space for registers if needed
		if (ps + 3) > registers:
			replace = replace.replace('.registers %d' % registers, '.registers %d' % (registers + abs(registers - ps - 3)))
			registers = registers + abs(registers - ps - 3)

		# Inject our debug code
		debug = '\n' \
			+ '    const/4 v0, 0x6\n' \
			+ '    const-string v1, "%s"\n' % TAG \
			+ '    const-string v2, "%s"\n' % ('%s(%s) in %s (%s)' % (source if source else _class[1:-1], method, smali, _class)) \
			+ '    invoke-static {v0, v1, v2}, Landroid/util/Log;->println(ILjava/lang/String;Ljava/lang/String;)I\n'

		replace = replace.replace('.registers %d' % registers, '.registers %d\n    %s' % (registers, debug))

		# Final replace
		code = code.replace(original, replace)

	f.seek(0)
	f.write(code)
	f.close()
