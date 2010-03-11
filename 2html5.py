#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
======
2HTML5
======

:Author: James H. Fisher
:Date: 9 March 2010
:License: MIT

This script takes any old HTML and outputs pristine HTML5.
You'll want:

- BeautifulSoup
- html5lib
- lxml
"""


"""
Imports
-------
"""

# Standard library imports

import sys
from os.path import splitext
from optparse import OptionParser

# External library imports

from BeautifulSoup import BeautifulSoup   # De-shit shitty HTML
import html5lib
from html5lib import treebuilders
from lxml import etree, html


"""
The meat of it: the algorithms
------------------------------
"""

def uniqify(seq, idfun=None):
  # Taken from http://www.peterbe.com/plog/uniqifiers-benchmark
  if idfun is None:
    def idfun(x): return x
  seen = {}
  result = []
  for item in seq:
    marker = idfun(item)
    # in old Python versions:
    # if seen.has_key(marker)
    # but in new ones:
    if marker in seen: continue
    seen[marker] = 1
    result.append(item)
  return result


headings = {
  'h1': 6,
  'h2': 5,
  'h3': 4,
  'h4': 3,
  'h5': 2,
  'h6': 1
  }
reverse_headings = dict((v,k) for k, v in headings.iteritems())  # http://stackoverflow.com/questions/483666/python-reverse-inverse-a-mapping
heading_xpath = '|'.join(['//'+heading for heading in headings.keys()])
heading_child_xpath = '|'.join(headings.keys())

  
def hgroupise(tree):
  """
  Given an HTML tree, surround headings with hgroups as appropriate.
  This involves:
  
  1. Go to the next h1-h6, X.
  2. If X is the member of an <hgroup>, go to 1.
  3. Place an <hgroup> H as X's previous sibling.
  4. Read through X's next siblings,
     appending them to H,
     until reaching one that isn't:
     
     * An h1-h6
     * A <br />
  
  5. If H contains only one element,
     move all elements as H's next siblings,
     then remove H.
  """
    
  def has_content(el):
    """
    Determine whether an element has significant content.
    Effectively, 'is there text here?'
    """
    if el.__class__.__name__ == '_Comment':
      # There should be something better than this
      return False
      
    try:
      el_text = el.text.strip()
    except AttributeError:
      el_text = ''
    if el_text:
      return True
    for e in el.iterchildren():
      if not e.__class__.__name__ == "_Comment":
        try:
          text = e.text.strip()
        except AttributeError:
          text = ''
        try:
          tail = e.tail.strip()
        except AttributeError:
          tail = ''
        if text or tail or has_content(e):
          return True
    return False
  
  for heading in tree.xpath(heading_xpath):
    if len(heading.xpath('ancestor::hgroup')) > 0:      # If the heading is in an hgroup already,
      continue                                            # it's already done.
    
    hgroup = etree.Element("hgroup")                    # The new hgroup
    
    parent = heading.getparent()
    start_index = parent.index(heading)
    parent.insert(start_index, hgroup)                  # Place the hgroup before parent
    
    for following in hgroup.itersiblings():             # Go through following siblings
      if following.tag in headings.keys() or not has_content(following): # If they're appropriate hgroup material,
        hgroup.append(following)                          # include them.
      else:                                             # Otherwise,
        break                                             # Stop including elements.
    
    if len(hgroup) < 2:                                 # If it turns out the heading was lone,
      for child in reversed(hgroup):                      # put the moved siblings back,
        parent.insert(start_index+1, child)
      parent.remove(hgroup)                               # and remove the hgroup.


def hgroup_value(el):
  """
  Find the equivalent value of an <hgroup> compared to a stand-alone
  <hx> element.
  This is just equal to the value of the highest-value <hx> child element.
  """
  return max([headings[h.tag] for h in el.xpath(heading_child_xpath)])

def heading_element_value(el):
  if el.tag == 'hgroup':
    return hgroup_value(el)
  return headings[el.tag]

def get_heading_elements(tree):
  heading_elements = tree.xpath(heading_xpath)  # Get all headings.
  
  for i in xrange(len(heading_elements)): # Replace headings with hgroups where they are present
    hgroups = heading_elements[i].xpath('ancestor::hgroup')
    if len(hgroups) > 0:
      heading_elements[i] = hgroups[0]
  
  return uniqify(heading_elements)  # Remove duplicates (hgroups should have more than one heading child)


def sectionise(tree):
  """
  Surround sections of the document with <section> tags
  where all the content is supposed to lie under one heading.
  
  1. Go to next heading tag, h1 to h6, hX.
  2. If hX has an <hgroup> ancestor, set the hX=ancestor, with value X.
  3. Get parent P of hX.
  4. If P is a <section>, go to 1.
  5. Insert a <section> S as the previous sibling of hX.
  6. Find first child of P, if any, namely hY, that satisfies:
     * It appears after hX
     * Y ≥ X
  7. Move all nodes between hX (inclusive) and hY (exclusive), or until the last child of P, into S.
  8. Go to 1.
  """
  
  heading_elements = get_heading_elements(tree)
  
  for i in reversed(xrange(len(heading_elements))): # Remove those with <section> parents
    if heading_elements[i].getparent().tag == 'section':
      heading_elements.pop(i)
  
  for heading in heading_elements:
    if heading.tag == 'hgroup':
      value = hgroup_value(heading)
    else:
      value = headings[heading.tag]
  
    parent = heading.getparent()
    
    start_index = parent.index(heading)
    
    section = etree.Element("section")
    parent.insert(start_index, section)
    
    section.append(heading)
    
    for following in section.itersiblings():
      
      tag = following.tag
      
      if tag in headings.keys() or tag == 'hgroup':
        
        if tag == 'hgroup':
          val = hgroup_value(following)
        else:
          val = headings[tag]
        
        if val >= value:
          break
        
      section.append(following)

def normalize(tree):
  """
  Take all headings in the tree, and normalize them.
  This basically means "set all headings to <h1>s",
  except for <hgroup>s where the top-level heading is set to <h1>.
  """
  for heading in get_heading_elements(tree):
    if heading.tag == 'hgroup':
      increase = 6 - heading_element_value(heading)  # Amount to increase this heading element
      for h in heading.xpath(heading_child_xpath):
        val = headings[h.tag]
        h.tag = reverse_headings[val + increase]
    else:
      heading.tag = reverse_headings[6] # Maximum heading
    

"""
Parse command-line options
--------------------------
"""

usage = \
"""usage: %prog [options] [infile [outfile]].

| I perform automated conversions to HTML5.
| I take HTML from `infile`, and do the following:
|
| - if `--hgroup` is specified, I group sequences of headings in <hgroup> tags.
| - if `--section` is specified, I then wrap <section> tags appropriately around headings.
| - if `--normalize` is specified, I finally transform all heading tags to be top-level.
|
| For best results:
|  1. run with `--hgroup`
|  2. manually:
|     - split mistaken <hgroup>s where they've covered more than one multiple-level heading
|     - merge <hgroup>s where elements have prevented covering multiple-level headings
|  3. run with `--section` and `--normalize`.
|
| If `--replace` is specified, I write back to the file.
| Otherwise, if `outfile` is specified, I write to that.
| Otherwise, I write to stdout."""

parser = OptionParser(usage=usage)

parser.add_option('-g', '--hgroup', action="store_true",
                  help="Group headings.")
parser.add_option('-s', '--section', action="store_true",
                  help="Group sections.")
parser.add_option('-n', '--normalize', action="store_true",
                  help="Normalize headings.")
parser.add_option('-r', '--replace', action="store_true",
                  help="Replace the original file with the output. "
                       "Use with caution!")
                  
options, args = parser.parse_args()


if not options.hgroup and not options.section:
  print "You haven't asked me to do anything! (use `--hgroup` to attempt heading grouping.)"
  sys.exit(1)


"""
Sort out files and build the input tree
---------------------------------------
"""

infilepath = args[0]
infile = open(infilepath, 'r')
inhtml = infile.read()
infile.close()

if options.replace:
  outfile = open(infilepath, 'w')
else:
  try:
    outfilepath = args[1]
  except IndexError:
    outfile = sys.stdout
  else:
    outfile = open(outfilepath, 'w')

soup = BeautifulSoup(inhtml)

parser = html5lib.HTMLParser(tree=treebuilders.getTreeBuilder("lxml"))
doc = parser.parse(soup.prettify())


"""
Convert headings to hgroups where appropriate
---------------------------------------------
"""

if options.hgroup:
  hgroupise(doc)
if options.section:
  sectionise(doc)
if options.normalize:
  normalize(doc)

"""
Write to the output
-------------------
"""

doctype_declaration = "<!DOCTYPE html>\n"
output = etree.tostring(doc, pretty_print=True)

if not output.startswith(doctype_declaration):
  outfile.write(doctype_declaration)

outfile.write( html.tostring(doc, encoding='utf-8', method='xml') )

