import json
import time

status = ["current", "completed", "paused", "dropped", "planning"]
mk_status = ["Currently reading", "Completed", "Paused", "Dropped", "Plan to read"]

markdown = ""

for i, stat in enumerate(status):
	status_file = "manga_" + stat + ".json"
	
	with open(f'lists/{status_file}', encoding='utf8') as f:
		data = json.load(f)

	mediaList = data["mediaList"]

	if mediaList:
		markdown += f"# {mk_status[i]} ({data['total']})\n\n"
		for entry in mediaList:
			progress = entry['progress']
			total = entry['media']['chapters'] or '?'
			markdown += f"- {entry['media']['title']['romaji']} ({progress}/{total})\n"
		markdown += "\n"

markdown = markdown.rstrip()
markdown += "\n"

with open(f"lists/mangalist_{str(time.time()).split('.')[0]}.md", "w", encoding='utf8') as f:
	f.write(markdown)
print("Done")
