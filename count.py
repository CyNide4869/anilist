import json

with open('lists/anime_completed.json', encoding='utf8') as f:
	contents = json.load(f)
	total = contents["total"]
	mediaList = contents["mediaList"]

bitmap = []
complete = []

for entry in mediaList:
	media = entry["media"]
	adult = media["isAdult"]
	# if adult:
	# 	print("Romaji:", media["title"]["romaji"])
	# 	print("English:", media["title"]["english"])
	# 	print("Format:", media["format"])
	# 	print("Custom Lists:", entry["customLists"][-1], entry["customLists"][-2], end="\n\n")
	relations = media["relations"]
	complete.append({
		"Romaji": media["title"]["romaji"],
		"English": media["title"]["english"],
		"Format": media["format"],
		"Custom Lists": entry["customLists"][0]
	})
	
	bitmap.append(1)
	edges = relations["edges"]
	if edges:
		for relation in edges:
			if relation["relationType"] == "PREQUEL" or adult or media["format"] != "TV":
				bitmap.pop()
				bitmap.append(0)
				break
	else:
		bitmap.pop()
		bitmap.append(0)

output = []

for i, bit in enumerate(bitmap):
	if bit:
		entry = mediaList[i]
		media = entry["media"]
		output.append({
			"Romaji": media["title"]["romaji"],
			"English": media["title"]["english"],
			"Format": media["format"],
			"Custom Lists": entry["customLists"][0]
		})

with open("out.json", "w", encoding="utf8") as f, open("completed.json", "w", encoding="utf8") as c:
	json.dump(output, f, ensure_ascii=False, indent=2)
	json.dump(complete, c, ensure_ascii=False, indent=2)