"""

Extract words out of a book/text and get their definitions.

"""
import argparse
import codecs
import collections
import sys
import json
import os
import re
import zipfile
from typing import Dict

from nltk import tokenize, WordNetLemmatizer
from nltk.corpus.reader import wordnet

import reverse_data

# TODO: needs:
# nltk.download('wordnet')

MIN_WORD_LEN = 1
SEP = '|||'


def main():
  p = argparse.ArgumentParser()
  p.add_argument('input_path', help='Path to a .txt file or similar containing ' 
                                    'the text/book to parse.')
  p.add_argument('output_path', help='Path to where the output .zip should '
                                     'be stored.')
  p.add_argument('--dictionary_path', default=reverse_data.NOAD,
                 help="Path to a Body.data file. "
                      f"Defaults to {reverse_data.NOAD}")
  p.add_argument('--input_encoding', '-i',
                 help='Encoding of the file at INPUT_PATH. By default, try'
                      'utf-8 and ISO-8859-1.')
  flags = p.parse_args()
  if not flags.output_path.endswith('.zip'):
    print('output_path should end in .zip')
    sys.exit(1)

  extract_definitions_from_text(flags.input_path,
                                flags.output_path,
                                flags.dictionary_path,
                                flags.input_encoding)


def extract_definitions_from_text(input_path,
                                  output_path,
                                  dictionary_path=reverse_data.NOAD,
                                  input_encoding=None):
  if not os.path.isfile(input_path):
    raise FileNotFoundError(input_path)


  word_dict = reverse_data.WordDictionary.from_file(dictionary_path)

  text = try_to_read(input_path, input_encoding)
  word_counts, links = _get_word_counts(text, word_dict)
  word_dict.add_links(links)

  scores = _get_scores(word_counts, word_dict)

  words = set(word_counts.keys())
  _write_filtered_dict(words, word_dict, scores, text, output_path)
  return list(word_counts.keys())


def try_to_read(input_path, input_encoding=None) -> str:
  if input_encoding:
    input_encodings = [input_encoding]
  else:
    input_encodings = ['utf-8', 'ISO-8859-1', 'ascii']

  for encoding in input_encodings:
    try:
      with codecs.open(input_path, mode='r', encoding=encoding) as f:
        print(f'Decoded file with {encoding}.')
        return f.read()
    except UnicodeDecodeError as e:
      print(f'Caught {e}')

  raise ValueError("Hmm, file has unknown encoding.")


def _write_filtered_dict(words: set,
                         word_dict: reverse_data.WordDictionary,
                         scores: Dict[str, float],
                         text: str,
                         output_path: str):
  filtered_word_dict = word_dict.filtered(words)
  dict_of_str = {key: entry.content for key, entry in filtered_word_dict.items()}
  master_object = {
    'definitions': dict_of_str,
    'links': filtered_word_dict.links,
    'scores': scores}

  # Write definitions as JSON
  os.makedirs(os.path.dirname(output_path), exist_ok=True)
  with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
    zf.writestr('master.json', json.dumps(master_object).encode('utf-8'))
    zf.writestr('fulltext.txt', text.encode('utf-8'))


def _get_scores(word_counts: Dict[str, int],
                word_dict: reverse_data.WordDictionary) -> Dict[str, float]:
  """Very crude way to get scores from word_counts and a dictionary.

  Algorithm for a word `w`:
  1. Set score := how often does w occur in the text
     (as given by `word_counts`).
  2. If the word is said to be "literary" in the dict, divide score by 2.

  Overall, lower score means "rarer" words.
  """
  scores = {word: count for word, count in word_counts.items()}
  for word in word_counts:
    if 'literary' in word_dict[word].get_info():
      scores[word] /= 2
  return scores


def _get_word_counts(text: str,
                     word_dict: reverse_data.WordDictionary):
  """Given a text and a dictionary, split the text into words and return counts.

  Done by:
  1. Sanitize text by doing lower case and removing newlines.
  2. Use NLTK's tokenizer
  3. Try to find the base by using NLTK's lemmatizer (i.e. houses -> house),
     to increase chances of finding a word in the dictionary
  4. Count the occurences of words.
  """
  text = text.lower()

  print('Collapsing newlines...')
  text = re.sub('(.)\n', r'\1 ', text)

  print('Tokenizing...')
  words = tokenize.word_tokenize(text)

  print('Pruning...')

  # Remove punctuation in tokens, as ntlk tokenizes for example "they'll" as
  # [they, 'll]. The resulting "ll" will be ditched in a later stage.
  # Also removes tokens that are just quotes, which turn into empty tokens,
  # removed at the MIN_WORD_LEN stage below.
  words = (w.strip("'.-`\"") for w in words)
  # Ditches some genitives and third person singulars. In Python 3.9 this
  # should be `removesuffix` but the `replace` works well enough in this context.
  words = (w.replace("'s", '') for w in words)
  # Removes abbreviations such as "e.g."
  words = (w for w in words if '.' not in w)
  # Removes most punctuation from the list, such as ",", ":", etc.,
  # also removes empty tokens.
  words = (w for w in words if len(w) > MIN_WORD_LEN)
  # Removes all numbers
  words = (w for w in words if w and not all(c.isdigit() for c in w))
  
  print('Counting...')
  word_counts = collections.Counter(words)

  print('Lemmatizing...')
  lemma = WordNetLemmatizer()
  word_counts_lemmad = collections.defaultdict(int)

  # We create a map from word_as_it_appears_in_book to the lemmad
  # words to simplify lookup later. Note that it's not exactly
  # word_as_it_appears_in_book due to the preprocessing above but oh well.
  links = {}

  # Note: assume we have `word_counts` = {"belongs": 4 "belonging":3}
  # This results in sth like {"belong": 7, "belonging": 7} in the following.
  for w, count in word_counts.items():
    possible_words = []
    if w in word_dict:
      possible_words.append(w)
      word_is_in_dict = True
    else:
      word_is_in_dict = False

    for t in wordnet.POS_LIST:
      w_lemmad = lemma.lemmatize(w, pos=t)
      if w_lemmad != w and w_lemmad in word_dict:
        possible_words.append(w_lemmad)

    # Neither the input word nor any lemmad forms are in the dictionary.
    if not possible_words:
      continue

    # Input word is not in dictionary but some lemmad form is.
    # We pick any random of the lemmad forms to make a link,
    # hoping it's a good one.
    if not word_is_in_dict:
      links[w] = next(iter(possible_words))

    # Build counts dict.
    for possible_w in possible_words:
      word_counts_lemmad[possible_w] += count

  return word_counts_lemmad, links


if __name__ == '__main__':
  main()
