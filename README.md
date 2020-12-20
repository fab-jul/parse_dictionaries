# parse_dictionaries


The following blog post contains some backgroud
about this repo: 
[Reverse-Engineering Apple Dictionary](https://fmentzer.github.io/posts/2020/dictionary/).

## Parsing with `reverse_data`.py


Parses the great Apple Dictionary
(for now tested with the New Oxfor American Dictionary).

Here is what the built-in Dictionary app gives for "handle":

<div align="center">
  <img src='assets/dictionary.png' width="70%"/>
</div>

And here is what this script gives (on a Mac), with

```bash
# New Oxford American Dictionary
# NOTE: might be at a different location for you!
NOAD='/System/Library/AssetsV2/ \
       com_apple_MobileAsset_DictionaryServices_dictionaryOSX/ \
       4094df88727a054b658681dfb74f23702d3c985e.asset/ \
       AssetData/ \
       New Oxford American Dictionary.dictionary/ \
       Contents/Resources/Body.data'

python reverse_data.py \ 
        --dictionary_path $NOAD --lookup handle --output_path lookup/lookup.html
```

<div align="center">
  <img src='assets/dictionary_myoutput.png' width="70%"/>
</div>

## Extracting words and definitions from a book with `extract.py`

If you want to split a book into all its words and look them all up,
you can use `extract.py`. This relies on `nltk` to properly get definitions,
e.g., to turn "he builds houses" into `["he", "build", "house"]`. 

```bash
python extract.py PATH_TO_BOOK.txt PATH_TO_OUTPUT.zip
```

The resulting zip file contains a single file `master.json`, which contains
three keys. Example:

```json
{
 "definitions": {
   "cozen": "<d:entry xmlns:d=...",
   "house": "<d:entry xmlns:d=...",
   "related": "<d:entry xmlns:d=...",
   "rod": "<d:entry xmlns:d=...",
   "...": "..."
 },
 "links": {
   "vitals": "vital",
   "...": "..."
 },
 "scores": {
   "cozen": 0.5,
   "house": 1.0,
   "related": 10.0,
   "rod": 20.0,
   "...": "..."
 }
}
```

- `definitions` are just definitions of all words.
- `links` contains links
to definitions, if a word in the book does not have it's own definition.
- `scores` is a crude estimate for how likely it is that the reader knows
a word, see the `_get_scores` in `extract.py`.

