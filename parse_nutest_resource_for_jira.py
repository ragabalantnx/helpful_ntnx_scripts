import sys
import urllib


url = sys.argv[1]

f = urllib.urlopen(url)
myfile = f.read()
f.close()
lines = myfile.split("\n")
resource_line_idx = next((idx for idx, line in enumerate(lines) if line.startswith("+----")), None)
output_lines = []
if resource_line_idx:
  lines = lines[resource_line_idx:]
  for line in lines:
    if line.startswith("|"):
      output_lines.append(line)

  output_lines[0] = output_lines[0].replace("|", "||")

  print("\n".join(output_lines))










