from flask import Flask, render_template, request
from dGraph_conn import dGraph_conn
from text_to_uri import standardized_uri
import pymysql
import csv, json
import spacy
import itertools
import pandas as pd
import re, math
from sklearn.neighbors import NearestNeighbors
import nltk
from nltk.stem import WordNetLemmatizer 
from nltk.corpus import stopwords


conceptnetNumberBatchModel = './models/mini.h5'
rel_db_name = 'AutographaMT_Staging'
lemmatizer = WordNetLemmatizer()
stopWords = set(stopwords.words('english'))

graph_conn = None
app = Flask(__name__)


@app.route('/')
def main():
	global graph_conn
	graph_conn = dGraph_conn()
	print(graph_conn)
	return render_template('admin.html')

@app.route('/smart_search')
def search_page():
	global graph_conn
	graph_conn = dGraph_conn()
	print(graph_conn)
	return render_template('smart_search.html')

@app.route('/supersmart_search')
def conceptsearch_page():
	global graph_conn
	graph_conn = dGraph_conn()
	print(graph_conn)
	return render_template('concept_search.html')

@app.route('/testpage')
def loadSomething():
	return "Something to show its working"

# @app.route('/images/<filename>')
# def provide_media(filename):
# 	file = open('./templates/images/'+filename)
# 	return file

@app.route('/dgraph/delete-all-nodes')
def delete_all():
	global graph_conn
	res = graph_conn.drop_all()
	return "success"


@app.route('/dgraph/test')
def test():
	global graph_conn
	print(graph_conn)
	graph_conn.drop_all()
	graph_conn.set_schema()
	graph_conn.create_data()
	graph_conn.query_data() # query for Alice
	graph_conn.delete_data() # delete Bob
	graph_conn.query_data() # query for Alice
	return "success"


@app.route('/dgraph/add-strongs')
def add_strongs():
	global graph_conn
	db = pymysql.connect(host="localhost",database=rel_db_name, user="root", password="password", charset='utf8mb4')
	cursor = db.cursor(pymysql.cursors.SSCursor)
	tablename = 'Greek_Strongs_Lexicon'
	nodename = 'Greek Strongs'

	# create a dictionary nodename
	dict_node = { 'dictionary': nodename
			}
	dict_node_uid = graph_conn.create_data(dict_node)
	print(dict_node_uid)

	cursor.execute("Select ID, Pronunciation, Lexeme, Transliteration, Definition, StrongsNumber, EnglishWord from "+tablename+" order by ID")

	count_for_test = 0
	while(True):
		next_row = cursor.fetchone()
		if not next_row:
			break
		# if count_for_test>50:
		# 	break
		count_for_test += 1
		strongID = next_row[0]
		Pronunciation = next_row[1]
		Lexeme = next_row[2]
		Transliteration = next_row[3]
		Definition = next_row[4]
		StrongsNumberExtended = next_row[5]
		EnglishWord = next_row[6]

		strong_node = {
			'StrongsNumber':strongID,
			'pronunciation': Pronunciation,
			'lexeme': Lexeme,
			'transliteration': Transliteration,
			'definition': Definition,
			'strongsNumberExtended': StrongsNumberExtended,
			'englishWord': EnglishWord,
			'belongsTo':{
				'uid': dict_node_uid
				}		
			}
		strong_node_uid = graph_conn.create_data(strong_node)
		print(strong_node_uid)


	cursor.close()
	db.close()
	return "success"

@app.route('/dgraph/add-tws')
def add_tws():
	global graph_conn
	tw_path = '../neo4j/tws.csv'
	nodename = 'translation words'

	# create a dictionary nodename
	dict_node = { 'dictionary': nodename
			}
	dict_node_uid = graph_conn.create_data(dict_node)
	print(dict_node_uid)

	count_for_test = 0
	with open(tw_path) as csv_file:
		csv_reader = csv.reader(csv_file, delimiter='\t')
		for row in csv_reader:
			# if count_for_test>50:
			# 	break
			count_for_test += 1

			sl_no = row[0]
			tw = row[1]
			Type = row[2]
			word_forms = row[3].split(',')
			description = row[4]
			tw_node = {
				'translationWord':tw,
				'slNo': sl_no,
				'twType': Type,
				'description':description,
				'belongsTo':{
				'uid': dict_node_uid
				}		
			}
			if len(word_forms)>0:
				tw_node['wordForms'] = word_forms
			tw_node_uid = graph_conn.create_data(tw_node)
			print(tw_node_uid)

	return "success"	

dictNode_query = '''
	query dict($dict_name:string){
	dict(func: eq(dictionary,$dict_name)){
		uid
	}
	}
'''

bookNode_query = '''
		query book($bib: string, $book: string){
		book(func: uid($bib))
		@normalize {
				~belongsTo @filter (eq(book,$book)){
				uid : uid
				}
		}
		}
	'''
allBookNodes_query = '''
		query book($bib: string){
		book(func: uid($bib))
		@normalize {
				~belongsTo {
				uid : uid
				}
		}
		}
	'''
chapNode_query = '''
		query book($chap: int, $book: string){
		chapter(func: uid($book))
		@normalize {
				~belongsTo @filter (eq(chapter,$chap)){
				uid : uid
				}
		}
		}
	'''
allChapNodes_query = '''
		query chapter($book: string){
		chapter(func: uid($book))
		@normalize {
				~belongsTo {
				uid : uid
				}
		}
		}
	'''

verseNode_query = '''
		query book($chapter: string, $verse: int){
		verse(func: uid($chapter))
		@normalize {
				~belongsTo @filter (eq(verse,$verse)){
				uid : uid
				}
		}
		}
	'''
allVerseNodes_query = '''
		query verse($chapter: string){
		verse(func: uid($chapter))
		@normalize {
				~belongsTo {
				uid : uid,
				verseEmbeddings(first:1){
					verseEmbeddings:uid
				}
				}
		}
		}
	'''
allWordNodes_query = '''
		query word($verse: string){
		word(func: uid($verse))
		@normalize {
				~belongsTo (orderasc: position){
				uid: uid,
				word: word
				}
		}
		}
	'''
verseNode_withLID_query = '''
		query verse($bib: string, $lid: int){
		verse(func: uid($bib))
		@normalize {
				~belongsTo {
					~belongsTo{
						~belongsTo @filter(eq(lid,$lid)){
						  uid: uid
		}	}	}	}	}
	'''
verseNode_withLID_query2 = '''
		query verse($bib: string, $lid: int){
		verse(func: eq(bible,$bib))
		@normalize @cascade{
				bible:bible,
				~belongsTo {
					book:book,
					~belongsTo{
						chapter:chapter,
						~belongsTo @filter(eq(lid,$lid)){
						  uid: uid,
						  verse:verse,
						  verseText:verseText
		}	}	}	}	}
	'''


twNode_query = '''
	query tw($word: string){
	tw(func: eq(translationWord, $word) ){
		uid
	}
	}
	'''
twNode_wordForms_query = '''

	query tw($word: string){
	tw(func: in(wordForms,$word)){
		uid
	}
	}
'''
strongNode_query = '''
	query strongs($strongnum: int){
	strongs(func: eq(StrongsNumber,$strongnum)){
		uid
	}
	}
'''

bible_query = '''
	query bible($name: string){
	bible (func: has(bible)) @filter(eq(bible,$name)){
	uid
	}
	}
'''

bible_word_query = '''
	query bib_word($bib:string, $book:int, $chapter:int, $verse:int, $pos:int){
	bib_word(func: uid($bib)) @normalize {
		~belongsTo @filter(eq(bookNumber,$book)){
			~belongsTo @filter(eq(chapter,$chapter)){
				~belongsTo @filter(eq(verse,$verse)){
					~belongsTo @filter(eq(position,$pos)){
						uid : uid
						
					}
				}
			}
		}
	}
	}
'''

search_word_query = '''
	query search_word($bib:string, $word:string){
	search_word(func: uid($bib)) @normalize {
		~belongsTo @filter(has(bookNumber)){
			~belongsTo @filter(has(chapter)){
				~belongsTo @filter(has(verse)){
					~belongsTo @filter(eq(word,$word)){
						uid : uid						
					}
				}
			}
		}
	}
}
'''

synonym_search_query = '''
	query synonym($syn_name:string){
	synonym(func: eq(synonym_set,$syn_name)){
		uid
	}
	}
'''

lemma_search_query = '''
	query lemma($wn_lemma:string){
	lemma(func: eq(wn_lemma,$wn_lemma)){
		uid
	}
	}
'''

cnTerm_query = '''
	query terms($term: string){
	terms(func: eq(cn_term,$term)){
	uid,
	cn_term,
	~verseEmbeddings{
		verse,
		verseText,
		belongsTo{
			chapter,
			belongsTo{
				book,
				belongsTo{
				 bible
				}
			}
		}
	}
	}
	}

'''

all_cnTerm_query = '''
	query terms($something: string){
	terms(func: has(cn_term)){
	cn_term,
	~verseEmbeddings{
		lid
	}	}	}

'''

@app.route('/dgraph/add-ugnt')
def add_ugnt_bible():
	global graph_conn
	db = pymysql.connect(host="localhost",database=rel_db_name, user="root", password="password", charset='utf8mb4')
	cursor = db.cursor(pymysql.cursors.SSCursor)
	tablename = 'Grk_UGNT4_BibleWord'
	bib_name = 'Grk UGNT4 bible'

	bibNode_query_res = graph_conn.query_data(bible_query,{'$name':bib_name})
	if len(bibNode_query_res['bible']) == 0:
		# create a bible nodename
		bib_node = { 'bible': bib_name,
			'language' : 'Greek',
			'version': "4.0"
				}
		bib_node_uid = graph_conn.create_data(bib_node)
		print(bib_node_uid)
	elif len(bibNode_query_res['bible']) > 1:
		print("matched multiple bible nodes")
		return
	else:
		bib_node_uid = bibNode_query_res['bible'][0]['uid']


	Morph_sequence = ['Role','Type','Mood','Tense','Voice','Person','Case','Gender','Number','Degree']
	

	cursor.execute("Select LID, Position, Word, Strongs, Morph, Pronunciation, Map.Book, Chapter, Verse,lookup.Book, TW from "+tablename+" JOIN Bcv_LidMap as Map ON LID=Map.ID JOIN Bible_Book_Lookup as lookup ON lookup.ID=Map.Book where lookup.ID = %s order by LID, Position",(40))
	# cursor.execute("Select LID, Position, Word, Strongs, Morph, Pronunciation, Map.Book, Chapter, Verse,lookup.Book, TW from "+tablename+" JOIN Bcv_LidMap as Map ON LID=Map.ID JOIN Bible_Book_Lookup as lookup ON lookup.ID=Map.Book where lookup.ID > %s order by LID, Position",(39))

	count_for_test = 0
	chapNode=None
	while(True):
		next_row = cursor.fetchone()
		if not next_row:
			break
		# if count_for_test>100:
		# 	break
		count_for_test += 1


		LID = next_row[0]
		Position = next_row[1]
		Word = next_row[2]
		Strongs = next_row[3]
		Morph = next_row[4].split(',')
		Pronunciation = next_row[5]	
		BookNum = next_row[6]
		Chapter = next_row[7]
		Verse = next_row[8]
		BookName = next_row[9]
		TW_fullString = next_row[10]
		print('Book,Chapter,Verse:'+str(BookNum)+","+str(Chapter)+","+str(Verse))

		# to find/create book node
		variables = {
			'$bib': bib_node_uid,
			'$book': BookName
		}
		bookNode_query_res = graph_conn.query_data(bookNode_query,variables)
		if len(bookNode_query_res['book']) == 0:
			bookNode = {
				'book' : BookName,
				'bookNumber': BookNum,
				'belongsTo' : {
					'uid': bib_node_uid 
				}
			}
			bookNode_uid = graph_conn.create_data(bookNode)
		elif len(bookNode_query_res['book']) > 1:
			print('matched multiple book nodes!')
			break
		else:
			bookNode_uid = bookNode_query_res['book'][0]['uid']
		# print('bookNode_uid:',bookNode_uid)

		# to find/create chapter node
		variables = {
			'$book': bookNode_uid,
			'$chap': str(Chapter)
		}
		try:
			chapNode_query_res = graph_conn.query_data(chapNode_query,variables)
		except Exception as e:
			print('chapNode_query threw error')
			# return "error"
		if len(chapNode_query_res['chapter']) == 0:
			chapNode = {
				'chapter' : Chapter,
				'belongsTo' : {
					'uid': bookNode_uid 
				}
			}
			chapNode_uid = graph_conn.create_data(chapNode)
		elif len(chapNode_query_res['chapter']) > 1:
			print('matched multiple chapter nodes!')
			break
		else:
			chapNode_uid = chapNode_query_res['chapter'][0]['uid']
		# print('chapNode_uid:',chapNode_uid)

		# to find/create verse node
		variables = {
			'$chapter': chapNode_uid,
			'$verse': str(Verse)
		}
		verseNode_query_res = graph_conn.query_data(verseNode_query,variables)
		if len(verseNode_query_res['verse']) == 0:
			verseNode = {
				'verse' : Verse,
				'belongsTo' : {
					'uid': chapNode_uid 
				},
				'lid':LID
			}
			verseNode_uid = graph_conn.create_data(verseNode)
		elif len(verseNode_query_res['verse']) > 1:
			print('matched multiple verse nodes!')
			break
		else:
			verseNode_uid = verseNode_query_res['verse'][0]['uid']
		# print('verseNode_uid:',verseNode_uid)

		# to create a word node
		wordNode = {
				'word' : Word,
				'belongsTo' : {
					'uid': verseNode_uid 
				},
				'position': Position,
				'pronunciation':Pronunciation
			}
		for key,value in zip(Morph_sequence,Morph):
			if(value!=''):
				wordNode[key] = value
		variables = {
			'$strongnum': str(Strongs)
		}
		strongNode_query_res = graph_conn.query_data(strongNode_query,variables)
		print('strongNode_query_res:',strongNode_query_res)
		if len(strongNode_query_res['strongs'])>0:
			strongNode_uid = strongNode_query_res['strongs'][0]['uid']
			wordNode['lemma'] = { 'uid': strongNode_uid }
		if TW_fullString != "-":
			Type, word = TW_fullString.split('/')[-2:]
			variables = {
				'$word' : word
			}
			twNode_query_res = graph_conn.query_data(twNode_query,variables)
			# print('twNode_query_res:',twNode_query_res)
			if len(twNode_query_res['tw']) > 0:
				twNode_uid = twNode_query_res['tw'][0]['uid']
				wordNode['tw'] = { 'uid': twNode_uid }

		
		
		wordNode_uid = graph_conn.create_data(wordNode)
		print('wordNode_uid:',wordNode_uid)

	cursor.close()
	db.close()
	return "success"

@app.route('/dgraph/add-bible')
def add_bible():
	global graph_conn

	lang = request.args.get('lang', default = 'Hin', type = str)
	version = request.args.get('version', default = 'IRV4', type = str)

	db = pymysql.connect(host="localhost",database=rel_db_name, user="root", password="password", charset='utf8mb4')
	cursor = db.cursor(pymysql.cursors.SSCursor)
	tablename = lang+'_'+version+'_BibleWord'
	bib_name = lang+' '+version+' bible'

	bibNode_query_res = graph_conn.query_data(bible_query,{'$name':bib_name})
	if len(bibNode_query_res['bible']) == 0:
		# create a bible nodename
		bib_node = { 'bible': bib_name,
			'language' : lang,
			'version': version
				}
		bib_node_uid = graph_conn.create_data(bib_node)
		print("created bible node:",bib_node_uid)
	elif len(bibNode_query_res['bible']) > 1:
		print("matched multiple bible nodes")
		return
	else:
		bib_node_uid = bibNode_query_res['bible'][0]['uid']

	cursor.execute("Select LID, Position, Word, Map.Book, Chapter, Verse,lookup.Book from "+tablename+" JOIN Bcv_LidMap as Map ON LID=Map.ID JOIN Bible_Book_Lookup as lookup ON lookup.ID=Map.Book where lookup.ID=%s order by LID, Position",(56))
	# cursor.execute("Select LID, Position, Word, Map.Book, Chapter, Verse,lookup.Book from "+tablename+" JOIN Bcv_LidMap as Map ON LID=Map.ID JOIN Bible_Book_Lookup as lookup ON lookup.ID=Map.Book where lookup.ID>%s order by LID, Position",(39))
	# cursor.execute("Select LID, Position, Word, Map.Book, Chapter, Verse,lookup.Book from Eng_ULB_BibleWord JOIN Bcv_LidMap as Map ON LID=Map.ID JOIN Bible_Book_Lookup as lookup ON lookup.ID=Map.Book where lookup.ID=40  and LID>=23806 and Position > 18 order by LID, Position")

	count_for_test = 0
	while(True):
		next_row = cursor.fetchone()
		if not next_row:
			break
		# if count_for_test>10:
		# 	break
		count_for_test += 1

		LID = next_row[0]
		Position = next_row[1]
		Word = next_row[2]
		BookNum = next_row[3]
		Chapter = next_row[4]
		Verse = next_row[5]
		BookName = next_row[6]

		# to find/create book node
		variables = {
			'$bib': bib_node_uid,
			'$book': BookName
		}
		bookNode_query_res = graph_conn.query_data(bookNode_query,variables)
		if len(bookNode_query_res['book']) == 0:
			bookNode = {
				'book' : BookName,
				'bookNumber': BookNum,
				'belongsTo' : {
					'uid': bib_node_uid 
				}
			}
			bookNode_uid = graph_conn.create_data(bookNode)
		elif len(bookNode_query_res['book']) > 1:
			print('matched multiple book nodes!')
			break
		else:
			bookNode_uid = bookNode_query_res['book'][0]['uid']
		# print('bookNode_uid:',bookNode_uid)

		# to find/create chapter node
		variables = {
			'$book': bookNode_uid,
			'$chap': str(Chapter)
		}
		try:
			chapNode_query_res = graph_conn.query_data(chapNode_query,variables)
		except Exception as e:
			print('chapNode_query threw error')
			# return "error"
		if len(chapNode_query_res['chapter']) == 0:
			chapNode = {
				'chapter' : Chapter,
				'belongsTo' : {
					'uid': bookNode_uid 
				}
			}
			chapNode_uid = graph_conn.create_data(chapNode)
		elif len(chapNode_query_res['chapter']) > 1:
			print('matched multiple chapter nodes!')
			break
		else:
			chapNode_uid = chapNode_query_res['chapter'][0]['uid']
		# print('chapNode_uid:',chapNode_uid)

		# to find/create verse node
		variables = {
			'$chapter': chapNode_uid,
			'$verse': str(Verse)
		}
		verseNode_query_res = graph_conn.query_data(verseNode_query,variables)
		if len(verseNode_query_res['verse']) == 0:
			verseNode = {
				'verse' : Verse,
				'belongsTo' : {
					'uid': chapNode_uid 
				},
				'lid':LID
			}
			verseNode_uid = graph_conn.create_data(verseNode)
		elif len(verseNode_query_res['verse']) > 1:
			print('matched multiple verse nodes!')
			break
		else:
			verseNode_uid = verseNode_query_res['verse'][0]['uid']
		# print('verseNode_uid:',verseNode_uid)

		# to create a word node
		wordNode = {
				'word' : Word,
				'belongsTo' : {
					'uid': verseNode_uid 
				},
				'position': Position
			}
		wordNode_uid = graph_conn.create_data(wordNode)
		print('wordNode_uid:',wordNode_uid)

	cursor.close()
	db.close()
	# bib_node_uid = '0xa2689'
	# lang = 'Eng'
	# version = 'ULB'
	add_verseTextToBible(bib_node_uid,lang,version)
	add_wordEmbeddingToBibleVerse(bib_node_uid)
	return "success"

def add_verseTextToBible(bib_node_uid,lang,version):
	global graph_conn
	db = pymysql.connect(host="localhost",database=rel_db_name, user="root", password="password", charset='utf8mb4')
	cursor = db.cursor(pymysql.cursors.SSCursor)

	text_tablename = lang+'_'+version+'_Text'


	###### to add text from the text tables in the mysql DB ###############
	cursor.execute("SELECT LID, main.Verse from "+text_tablename+" as main JOIN Bcv_LidMap as Map ON LID=Map.ID JOIN Bible_Book_Lookup as lookup ON lookup.ID=Map.Book where lookup.ID=%s order by LID",(56))
	# cursor.execute("SELECT LID, main.Verse from "+text_tablename+" as main JOIN Bcv_LidMap as Map ON LID=Map.ID JOIN Bible_Book_Lookup as lookup ON lookup.ID=Map.Book where lookup.ID>%s order by LID",(39))
	next_row = cursor.fetchone()
	print("Adding text to the bible verse")
	while next_row:
		# print(next_row)
		LID = next_row[0]
		verse = next_row[1]
		variables = {
			'$bib': bib_node_uid,
			'$lid': str(LID)
		}
		verseNode_query_res = graph_conn.query_data(verseNode_withLID_query,variables)
		if len(verseNode_query_res['verse']) == 0:
			print('Couldn\'t find the verse with lid')
		elif len(verseNode_query_res['verse']) > 1:
			print('matched multiple book nodes!')
			break
		else:
			verseNode_uid = verseNode_query_res['verse'][0]['uid']
			verseText = {
				'uid': verseNode_uid,
				'verseText': verse 
			}
			graph_conn.create_data(verseText)
			print('text added for:',LID )
		next_row = cursor.fetchone()
		# break
	cursor.close()
	db.close()
	return "success"

def add_wordEmbeddingToBibleVerse(bib_node_uid):
	''' this method obtains the one word, two word and three word terms in the bible verses 
	and checks if it is a conceptnet concept. 
	If it has, then word embeddings from conceptnet's numberbatch will be added to the verse node''' 
	global graph_conn


	conceptnetNode_query_res = graph_conn.query_data(dictNode_query,{'$dict_name':'Conceptnet Numberbatch'})
	if len(conceptnetNode_query_res['dict']) == 0:
		# create a dict node for concept net
		conceptNetNode = {'dictionary':'Conceptnet Numberbatch'}

		conceptNetNode_uid = graph_conn.create_data(conceptNetNode)
		print("created conceptnet dictionary node:",conceptNetNode_uid)
	elif len(conceptnetNode_query_res['dict']) > 1:
		print("matched multiple conceptnet nodes")
		return
	else:
		conceptNetNode_uid = conceptnetNode_query_res['dict'][0]['uid']
		print('found Conceptnet node')
	test_count = 0
	## traverse the verse nodes of the bible
	variables = {'$bib':bib_node_uid}
	book_nodes = graph_conn.query_data(allBookNodes_query,variables)['book']
	for bookNode_uid in book_nodes:
		print('new book')
		variables = {'$book':bookNode_uid['uid']}
		chap_nodes = graph_conn.query_data(allChapNodes_query,variables)['chapter']
		for chapNode_uid in chap_nodes:
			print("new chapter")
			variables = {'$chapter':chapNode_uid['uid']}
			verse_nodes = graph_conn.query_data(allVerseNodes_query,variables)['verse']
			for verseNode in verse_nodes:
				print("new verse")
				verseNode_uid = verseNode['uid']
				if 'verseEmbeddings' in verseNode:
					print("Embedding already added. Skipping the verse!")
					continue
				variables = {'$verse':verseNode_uid}
				verse_words_res = graph_conn.query_data(allWordNodes_query,variables)
				verse_words = [node['word'] for node in verse_words_res['word']]
				verseTermEmbeddings = []
				## find possible terms 
				verseTerms = verse_words
				verseTerms = verseTerms + [' '.join(verse_words[i:i+2]) for i in range(len(verse_words)-1)]
				verseTerms = verseTerms + [' '.join(verse_words[i:i+3]) for i in range(len(verse_words)-2)]
				possible_uris = [standardized_uri('en',term) for term in verseTerms]
				# print('verseTerms:',verseTerms)
				# print('possible_uris:',possible_uris)
				embeds_inVerse = []
				for uri in possible_uris:
					try:
						vec = cn_embeddings.loc[uri] 
						# print(vec)
						embeds_inVerse.append((uri.replace('/c/en/',''),vec))
					except Exception as e:
						# print("misshit at conceptnet:",uri)
						pass
				# print(embeds_inVerse)
				# print('verseNode_uid:',verseNode_uid)

				for term in embeds_inVerse:
					termEmbed_uid= None
					cnTerm_query_res = graph_conn.query_data(cnTerm_query,{'$term':term[0]})
					if len(cnTerm_query_res['terms'])==0 :
						termEmbed = {
							'cn_term':term[0],
							# 'embedding':term[1],
							'belongsTo': {'uid':conceptNetNode_uid}}
						termEmbed_uid = graph_conn.create_data(termEmbed)
						print("added embedding for: ",term[0])
					elif len(cnTerm_query_res['terms'])>1:
						print('multiple term nodes matched for:',term[0])
						return
					else:
						termEmbed_uid = cnTerm_query_res['terms'][0]['uid']
					verseEmbedslink = {
						'uid': verseNode_uid,
						'verseEmbeddings': {'uid':termEmbed_uid}
					}
					graph_conn.create_data(verseEmbedslink)

				# test_count +=1
				# if test_count==10:
				# 	return


@app.route('/dgraph/add-alignment')
def add_alignment():
	global graph_conn

	lang_src = request.args.get('lang_src', default = 'Hin', type = str)
	version_src = request.args.get('version_src', default = '4', type = str)
	lang_trg = request.args.get('lang_trg', default = 'Grk', type = str)
	version_trg = request.args.get('version_trg', default = 'UGNT4', type = str)

	db = pymysql.connect(host="localhost",database=rel_db_name, user="root", password="password", charset='utf8mb4')
	cursor = db.cursor(pymysql.cursors.SSCursor)
	tablename = lang_src+'_'+version_src+'_'+lang_trg+'_'+version_trg+'_Alignment'
	alignment_name = lang_src+'-'+version_src+' '+lang_trg+'-'+version_trg+' Alignment'

	src_bib_name = lang_src+' '+version_src+' bible'
	variables = {
	'$name' : src_bib_name
	}
	src_bib_node_query_res = graph_conn.query_data(bible_query,variables)
	print('src_bib_node_query_res:',src_bib_node_query_res)
	src_bibNode_uid = src_bib_node_query_res['bible'][0]['uid']
	trg_bib_name = lang_trg+' '+version_trg+' bible'
	variables = {
	'$name' : trg_bib_name
	}
	trg_bib_node_query_res = graph_conn.query_data(bible_query,variables)
	try:
		trg_bibNode_uid = trg_bib_node_query_res['bible'][0]['uid']
	except Exception as e:
		print("query:",bible_query)
		print("variable:",variables)
		raise e
	cursor.execute("Select Book, Chapter, Verse, PositionSrc, PositionTrg, UserId, Stage, Type, UpdatedOn, LidSrc, LidTrg from "+tablename+" as a JOIN Bcv_LidMap as Map ON LidSrc=Map.ID where Map.Book = %s order by LidSrc, PositionSrc",(40))
	# cursor.execute("Select Book, Chapter, Verse, PositionSrc, PositionTrg, UserId, Stage, Type, UpdatedOn, LidSrc, LidTrg from "+tablename+" JOIN Bcv_LidMap as Map ON LidSrc=Map.ID where Map.Book >39 %s order by LidSrc, PositionSrc",(39))

	count_for_test = 0
	while(True):
		next_row = cursor.fetchone()
		# print(next_row)
		if not next_row:
			break
		# if count_for_test >10:
		# 	break
		count_for_test += 1

		BookNum = str(next_row[0])
		Chapter = str(next_row[1])
		Verse = str(next_row[2])
		PositionSrc = str(next_row[3])
		PositionTrg = str(next_row[4])
		UserId = str(next_row[5])
		Stage = str(next_row[6])
		Type = str(next_row[7])
		UpdatedOn = next_row[8]
		LidSrc = str(next_row[9])
		LidTrg = str(next_row[10])
		print('BCV:',(BookNum,Chapter,Verse))

		if PositionTrg == '255' or PositionSrc == '255':
			continue

		if (LidSrc != LidTrg):
			print("Across verse alignment cannot be handled by this python script.")
			print("Found at:",(BookNum,Chapter,Verse))
			sys.exit(1)

		src_wordNode_uid = None
		variables = {
			'$bib' : src_bibNode_uid,
			'$book' : str(BookNum),
			'$chapter' : str(Chapter),
			'$verse' : str(Verse),
			'$pos' : str(PositionSrc)
		}
		src_wordNode_query_res = graph_conn.query_data(bible_word_query,variables)
		src_wordNode_uid = src_wordNode_query_res['bib_word'][0]['uid']

		trg_wordNode_uid = None

		variables2 = {
			'$bib' : trg_bibNode_uid,
			'$book' : str(BookNum),
			'$chapter' : str(Chapter),
			'$verse' : str(Verse),
			'$pos' : str(PositionTrg)
		}
		try:
			trg_wordNode_query_res = graph_conn.query_data(bible_word_query,variables2)
			trg_wordNode_uid = trg_wordNode_query_res['bib_word'][0]['uid']
		except Exception as e:
			print('Query:',bible_word_query)
			print('variables',variables2)
			print(e)
			return
		print('src_wordNode_uid:',src_wordNode_uid)
		print('trg_wordNode_uid:',trg_wordNode_uid)

		set_alignment_mutation = { 'uid': src_wordNode_uid,
									'alignsTo': {
										'uid': trg_wordNode_uid
									}
								}
		res = graph_conn.create_data(set_alignment_mutation)
	cursor.close()
	db.close()
	return "success"

@app.route('/dgraph/add-wordnet')
def add_eng_wordnet():
	global graph_conn
	from nltk.corpus import wordnet as wn

	nodename = 'English Wordnet'

	bib_node_uid = graph_conn.query_data(bible_query,{'$name':'Eng ULB bible'})['bible'][0]['uid']
	if not bib_node_uid:
		print("Eng ULB bible not found!\nAborting... ")
		return "error"


	# create a dictionary nodename
	dict_node = { 'dictionary': nodename
			}
	dict_node_uid = graph_conn.create_data(dict_node)
	print(dict_node_uid)
	flag = False
	for i,word in enumerate(wn.words()):
		# if i <= 1000:
		# 	continue
		# if i>1000:
		# 	break
		# print(i)
		try:
			variables = {
				'$bib' : str(bib_node_uid),
				'$word' : word
			}
			search_word_query_res = graph_conn.query_data(search_word_query,variables)
			if len(search_word_query_res['search_word']) > 0:
				word_uids = search_word_query_res['search_word']
				# print(word_uids)

				wn_word_node = { 'wordnetWord': word,
								'belongsTo':{
									'uid': dict_node_uid
									}
								}
				wn_word_node_uid = graph_conn.create_data(wn_word_node)
				print(i,'. wordnetWord:',word,' @uid',wn_word_node_uid)
				for wrd in word_uids:
					# print('bible word:',wrd,'---->','wn word:',wn_word_node_uid)
					wn_link = { 'uid' : wrd['uid'],
								'wordnet_link' :{ 'uid' : wn_word_node_uid }
								}
					graph_conn.create_data(wn_link)
				for syn in wn.synsets(word):
					syn_node_uid = add_syn2wn(syn)
					syn_link = { 'uid': wn_word_node_uid,
								 'synset': {'uid': syn_node_uid}
								}
					# print('wn word:',wn_word_node_uid,'---->','synset:',syn_node_uid)
					graph_conn.create_data(syn_link)

					

		except Exception as e:
			print('wordnet portion threw error')
			raise(e)
			# return "error"
	return "success"

def add_syn2wn(syn):
	global graph_conn

	syn_node_res = graph_conn.query_data(synonym_search_query,{'$syn_name':syn.name()})
	syn_node_uid = None
	if len(syn_node_res['synonym'])>0:
		syn_node_uid = syn_node_res['synonym'][0]['uid']
	if not syn_node_uid:
		synset_node = {'synonym_set': syn.name(),
					   'definition':  syn.definition(),
					   'example': syn.examples()}
		syn_node_uid = graph_conn.create_data(synset_node)
		lemmas = syn.lemmas()
		for lma in lemmas:
			lma_node_res = graph_conn.query_data(lemma_search_query,{'$wn_lemma':lma.name()})
			lemma_node_uid = None
			if len(lma_node_res['lemma'])>0:
				lemma_node_uid = lma_node_res['lemma'][0]['uid']
			if not lemma_node_uid:
				lemma_node = {'wn_lemma':lma.name()}
				lemma_node_uid = graph_conn.create_data(lemma_node)
			# print(lemma_node_uid)
			lemma_link = {'uid': syn_node_uid,
						  'root': {'uid':lemma_node_uid}}
			# print('synset',syn_node_uid,'--->','lemma:',lemma_node_uid)
			graph_conn.create_data(lemma_link)
			antonyms = lma.antonyms()
			for anto in antonyms:
				ant_lma_node_res = graph_conn.query_data(lemma_search_query,{'$wn_lemma':anto.name()})
				ant_lemma_node_uid = None
				if len(ant_lma_node_res['lemma'])>0:
					ant_lemma_node_uid = ant_lma_node_res['lemma'][0]['uid']
				if not ant_lemma_node_uid:
					ant_lemma_node = {'wn_lemma':anto.name()}
					ant_lemma_node_uid = graph_conn.create_data(ant_lemma_node)
				# print(ant_lemma_node_uid)
				anto_link = { 'uid': lemma_node_uid,
							 'antonym': {'uid': ant_lemma_node_uid}
							}
				# print('wn word:',wn_word_node_uid,'---->','synset:',syn_node_uid)
				graph_conn.create_data(anto_link)
		hypernyms = syn.hypernyms()
		for hyp in hypernyms:
			hyp_node_uid = add_syn2wn(hyp)
			hyp_link = { 'uid': syn_node_uid,
						 'hypernym': {'uid': hyp_node_uid}
						}
			# print('wn word:',wn_word_node_uid,'---->','synset:',syn_node_uid)
			graph_conn.create_data(hyp_link)


	return syn_node_uid

@app.route('/dgraph/remove-wordnet')
def remove_eng_wordnet():
	global graph_conn

	wordnet_query = '''query itms($foo: string){
	itms(func: eq(dictionary,"English Wordnet")) @normalize {
		uid
	}
	}
	'''

	wordnetWord_query = '''query itms($foo: string){
	itms(func: has(wordnetWord)) {
			uid 
	}
	}
	'''

	synset_query = '''query itms($foo: string){
	itms(func: has(synonym_set)) {
			uid 
	}
	}
	'''

	lemma_query = '''query itms($foo: string){
	itms(func: has(wn_lemma)) {
			uid 
	}
	}
	'''

	delete_queries = [lemma_query, synset_query, wordnetWord_query, wordnet_query]
	for qry in delete_queries:
		print(qry)
		query_res = graph_conn.query_data(qry,{'$foo':''})
		print("about to delete:",query_res["itms"])
		if len(query_res["itms"]) > 0:
			graph_conn.delete_data(query_res['itms'])

	# query_res = graph_conn.query_data(lemma_query,{'$foo':''})
	# graph_conn.delete_data(query_res['itms'])

	return "success"
		
smart_search_query = '''
	query verses($word: string){
	  verses(func: eq(wn_lemma,$word))
	  @normalize @cascade{
	    search_word:wn_lemma
	    ~root{
	     ~synset{
	    		~wordnet_link{
	    			match_word:word
	    			belongsTo{
			            text:verseText,
			            verse_num:verse,
			            belongsTo{
			              chapter:chapter,
			              belongsTo{
			                book:book
	} }	} }	} }	} }
'''

over_smart_search_query = '''
	query verses($word: string){
	  verses(func: eq(wn_lemma,$word))
	  @normalize @cascade{
	    search_word:wn_lemma
	    ~root{
	     	~hypernym{
	     		~synset{
	    		~wordnet_link{
	    			match_word:word
	    			belongsTo{
			            text:verseText,
			            verse_num:verse,
			            belongsTo{
			              chapter:chapter,
			              belongsTo{
			                book:book
	     	
	} }	} }	} }	} } }
'''

plain_search_query = '''
	query verses($word: string){
		verses(func: eq(word,$word))
		@normalize @cascade{
			search_word: word,
			match_word: word,
			belongsTo{
			            text:verseText,
			            verse_num:verse,
			            belongsTo{
			              chapter:chapter,
			              belongsTo{
			                book:book
	}	}	}	}	}
'''

@app.route('/dgraph/ask/<search_query>',methods=["GET"])
def smart_search(search_query):
	global graph_conn

	search_terms = process_query(search_query)
	result = {}

	for search_term in search_terms:
		search_term = search_term.replace(" ","_")

		smart_search_res = graph_conn.query_data(smart_search_query,{'$word':search_term})
		over_search_res = graph_conn.query_data(over_smart_search_query,{'$word':search_term})
		plain_search_res = graph_conn.query_data(plain_search_query,{'$word':search_term})
		search_res = smart_search_res['verses'] + over_search_res['verses'] + plain_search_res['verses']
		
		for v in search_res:
			try:
				key = (v['book']+" "+str(v['chapter'])+':'+str(v['verse_num']))
				obj = {'clean_verse': v['text']}
				if key not in result:
					result[key] = obj
					entry ='\t'+v['text'].replace(v['match_word'],'<strong>'+v['match_word']+'</strong>')+'<br>' 
					result[key]['verse'] = entry
				else:
					entry =result[key]['verse'].replace(v['match_word'],'<strong>'+v['match_word']+'</strong>')
					result[key]['verse'] = entry

				
			except Exception as e:
				print(v)
				raise e

	result = sort_result_spacyBERT(result,search_query)
	# result2 = sort_result_conceptnet(result,search_terms)
	res_str = "BERT sorted<br>-----------<br>"+"".join([ key+result[key]['verse'] for i,key in enumerate(result) if i<10])
	# res_str += "<br>Conceptnet sorted<br>-----------<br>"+"".join([ key+result2[key]['verse'] for key in result2])
	res_str = json.dumps(res_str)
	return res_str

 
@app.route('/dgraph/ask2/<search_query>',methods=["GET"])
def smart_search2(search_query):
	global graph_conn

	search_terms = process_query(search_query)
	result = {}

	for search_term in search_terms:
		search_term = search_term.replace(" ","_")

		smart_search_res = graph_conn.query_data(smart_search_query,{'$word':search_term})
		over_search_res = graph_conn.query_data(over_smart_search_query,{'$word':search_term})
		plain_search_res = graph_conn.query_data(plain_search_query,{'$word':search_term})
		search_res = smart_search_res['verses'] + over_search_res['verses'] + plain_search_res['verses']
		
		for v in search_res:
			try:
				key = (v['book']+" "+str(v['chapter'])+':'+str(v['verse_num']))
				obj = {'clean_verse': v['text']}
				if key not in result:
					result[key] = obj
					entry ='\t'+v['text'].replace(v['match_word'],'<strong>'+v['match_word']+'</strong>')+'<br>' 
					result[key]['verse'] = entry
				else:
					entry =result[key]['verse'].replace(v['match_word'],'<strong>'+v['match_word']+'</strong>')
					result[key]['verse'] = entry

				
			except Exception as e:
				print(v)
				raise e

	# result = sort_result_spacyBERT(result,search_query)
	result2 = sort_result_conceptnet(result,search_terms)
	# res_str = "BERT sorted<br>-----------<br>"+"".join([ key+result[key]['verse'] for key in result])
	res_str = "<br>Conceptnet sorted<br>-----------<br>"+"".join([ key+result2[key]['verse'] for i,key in enumerate(result2) if i<10 ])
	res_str = json.dumps(res_str)
	return res_str

nlp = spacy.load('en_core_web_md')

def process_query(qry):
	qry_doc = nlp(qry)
	lemmas = [token.lemma_ for token in qry_doc if not token.is_stop]
	print('lemmas:',lemmas)
	return lemmas

# nlp_vec = spacy.load('en_core_web_vec')

def sort_result_spacyBERT(result_dict,qry):
	qry_doc = nlp(qry)
	for key  in result_dict:
		clean_text = result_dict[key]['clean_verse']
		clean_text_doc = nlp(clean_text)
		result_dict[key]['sim_score'] = qry_doc.similarity(clean_text_doc)
	
	sorted_res_list = sorted([(value['sim_score'],key,value) for key,value in result_dict.items()],reverse=True)
	sorted_result_dict = {}
	for score,key,value in sorted_res_list:
		sorted_result_dict[key]=value 

	return sorted_result_dict

def sort_result_conceptnet(result_dict,qry_terms):
	qry_embeddings = []
	for qt in qry_terms:
		try:
			vec = cn_embeddings.loc['/c/en/'+qt.replace(' ','_')] 
			qry_embeddings.append(vec)
		except Exception as e:
			print("misshit at conceptnet:",qt)
	for key  in result_dict:
		clean_text = result_dict[key]['clean_verse']
		verse_words = clean_text.split(' ')
		verse_terms = verse_words + [verse_words[i]+'_'+verse_words[i+1] for i in range(0,len(verse_words)-1)]
		verse_embeddings = []
		for vt in verse_terms:
			try:
				vec = cn_embeddings.loc['/c/en/'+vt] 
				verse_embeddings.append(vec)
			except Exception as e:
				print("misshit at conceptnet:",vt)
		sim_score = 0
		for qt,vt in itertools.product(qry_embeddings,verse_embeddings):
			cos = qt.dot(vt)
			if cos>0:
				sim_score += cos

		result_dict[key]['sim_score'] = sim_score

	sorted_res_list = sorted([(value['sim_score'],key,value) for key,value in result_dict.items()],reverse=True)
	sorted_result_dict = {}
	for score,key,value in sorted_res_list:
		sorted_result_dict[key]=value 

	return sorted_result_dict

aligned_to_greek_qry = '''
	query alignments($bible: string){
	 alignments(func: has(alignsTo)) @normalize @cascade {
	  word:word,
	  position:position,
	  belongsTo{
	   lid:lid,
	   verse:verseText,
	   belongsTo{
	   		chapter,
	   		belongsTo{
	   			book,
	   			belongsTo @filter(eq(bible,$bible)){
	   				bible
	   			}
	   		}	
	   }
	  },
	  alignsTo{
	   Type:Type
	  }

	 }
	}
'''

def unit_vec(vec):
    """
    Normalize a vector to a unit vector, so that dot products are cosine
    similarities.
    
    If it's the zero vector, leave it as is, so all its cosine similarities
    will be zero.
    """
    dot_prod = abs(vec.dot(vec))
    if dot_prod == 0:
        return vec
    try:
	    norm = dot_prod ** 0.5
    except Exception as e:
    	print("**************\ndot_prod:",dot_prod,"\n*****************")
    	return vec
    return vec / norm

@app.route('/dgraph/conceptsearch/<search_query>',methods=["GET"])
def concept_search(search_query):
	global graph_conn
	word_pattern = re.compile(r'\w+',re.UNICODE)
	qry_words = re.findall(word_pattern,search_query)
	qry_terms = []
	qry_terms = qry_words
	qry_terms = qry_terms + [' '.join(qry_words[i:i+2]) for i in range(len(qry_words)-1)]
	qry_terms = qry_terms + [' '.join(qry_words[i:i+3]) for i in range(len(qry_words)-2)]
	possible_uris = [standardized_uri('en',term) for term in qry_terms]
	qry_embeddings = []
	for uri in possible_uris:
		vec = None
		try:
			vec = cn_embeddings.loc[uri]
			qry_embeddings.append(unit_vec(vec))
		except Exception as e:
			# raise e
			pass
	# print('qry_embeddings:',qry_embeddings)
	all_cnTerm_query_res = graph_conn.query_data(all_cnTerm_query,{'$something':"so"})
	# print("all_cnTerm_query_res:",all_cnTerm_query_res)
	bible_terms_score = {}
	for item in all_cnTerm_query_res['terms']:
		vec = unit_vec(cn_embeddings.loc['/c/en/'+item['cn_term']])
		score = 0
		for emb in qry_embeddings:
			cos = vec.dot(emb)
			if cos >0:
				score += cos
		bible_terms_score[item['cn_term']] = score
	bible_verses_score = {}
	for term in bible_terms_score:
		lids = []
		score = bible_terms_score[term]
		for trm in all_cnTerm_query_res['terms']:
			if trm['cn_term'] == term:
				lids = [link['lid'] for link in trm['~verseEmbeddings']]
			for lid in lids:
				if lid in bible_verses_score:
					bible_verses_score[lid] += score
				else:
					bible_verses_score[lid] = score
	bible_verses_sorted = sorted(bible_verses_score, key=bible_verses_score.get,reverse=True)[:10]
	# print(bible_verses_sorted)
	result_str = ''
	for lid in bible_verses_sorted:
		verse_res = graph_conn.query_data(verseNode_withLID_query2,{'$bib':'Eng ULB bible','$lid':str(lid)})
		try:
			bcv = verse_res['verse'][0]['book']+' '+str(verse_res['verse'][0]['chapter'])+':'+str(verse_res['verse'][0]['verse'])
		except Exception as e:
			print(verse_res)
			raise e
		verseText = verse_res['verse'][0]['verseText']
		result_str += '<br>'+bcv+'&nbsp;'+verseText

	return json.dumps(result_str)

cn_embeddings = pd.read_hdf(conceptnetNumberBatchModel, 'mat', encoding='utf-8')
en_uris = [lab for lab in cn_embeddings.index if '/c/en/' in lab]
en_cnembeddings = cn_embeddings[cn_embeddings.index.isin(en_uris)]

# nn_model = NearestNeighbors(n_neighbors=10)
# nn_model.fit(en_cnembeddings)

concept_search_query = '''
	query verses($term: string){
		verses(func: eq(cn_term,$term)) @normalize @cascade{
			cn_term:cn_term,
			~verseEmbeddings{
				verseText:verseText,
				verseNumber:verse,
				belongsTo{
					chapter:chapter,
					belongsTo{
						book:book
	}	}	}	}	}
'''


@app.route('/dgraph/conceptsearch2/<search_query>',methods=["GET"])
def concept_search2(search_query):
	global graph_conn
	word_pattern = re.compile(r'\w+',re.UNICODE)
	qry_words = re.findall(word_pattern,search_query)
	qry_terms = []
	qry_terms = qry_words
	qry_terms = qry_terms + [' '.join(qry_words[i:i+2]) for i in range(len(qry_words)-1)]
	qry_terms = qry_terms + [' '.join(qry_words[i:i+3]) for i in range(len(qry_words)-2)]
	qry_embeddings = []
	related_cnterms = [] 
	for trm in qry_terms:
		vec = None
		possible_uri = standardized_uri('en',trm) 
		try:
			vec = en_cnembeddings.loc[possible_uri]
			qry_embeddings.append(unit_vec(vec))
			related_cnterms.append(possible_uri.split('/')[-1])
		except Exception as e:
			# raise e
			# print(trm,":ignores Exception")
			# print(e)
			pass
	for embed in qry_embeddings:
		nearestvects = nn_model.kneighbors([embed],30)
		related_cnterms += [(en_cnembeddings.index[index].split('/')[-1],nearestvects[0][0][i]) for i,index in enumerate(nearestvects[1][0])]
	verses = {}
	for term in related_cnterms:
		# print(term[0])
		concept_search_res = graph_conn.query_data(concept_search_query,{'$term':term[0]})
		# print(concept_search_res)
		for ver in concept_search_res['verses']:
			ref = ver['book']+ ' '+str(ver['chapter'])+":"+str(ver['verseNumber'])
			# print(ref)
			if ref in verses:
				try:
					verses[ref]['distscore'] += term[1]
					# pass
				except Exception as e:
					print("verses[ref]['distscore']:",verses[ref]['distscore'])
					if term[1] == 'n':
						pass
					else:
						raise e
			else:
				distscore = 0.0
				if type(term[1]) == 'numpy.float64':
					distscore = term[1]
					print(term[1])
				verses[ref] = {'verseText':ver['verseText'], 'distscore':distscore}
	sorted_verses = {k:v for k,v in sorted(verses.items(), key=lambda x: x[1]['distscore'])}
	result_str = ''
	for item in list(sorted_verses)[:10]:
		result_str +='<br>'+item+"&nbsp;"+sorted_verses[item]['verseText']
	return json.dumps(result_str)



@app.route('/dgraph/transferPOS/<lang>',methods=["GET"])
def transfer_POS(lang):		
	global graph_conn

	if lang == "hin":
		try:
			nlp = spacy.load('models/model-final')
			# pass
		except Exception as e:
			print("!!!!!!!Error in loading the model!!!!!!!!!")
			raise e
		bible = "Hin 4 bible"
	elif lang == "eng":
		bible = "Eng ULB bible"

	all_alignments = graph_conn.query_data(aligned_to_greek_qry,{'$bible':bible})['alignments']
	file =  open('transferedPOS.csv','w')
	file.write('lid\tposition\tword\tGreekPOS\tEngPOS\n')
	prev_lid = 0
	for alignment in all_alignments:
		word = alignment['word']
		position = alignment['position']
		lid = alignment['lid']
		verse = alignment['verse']
		greekTag = alignment['Type']

		if lid != prev_lid:
			spacyPosTags = []
			try:
				verse_doc = nlp(verse)
			except Exception as e:
				print('verse:',verse)
				raise e
			for token in verse_doc:
					spacyPosTags.append((token.text,token.tag_))
		
		engTag = None
		if spacyPosTags[position][0] == word:
			engTag = spacyPosTags[position][1]
		else:
			window_start = 0
			window_end = len(spacyPosTags)-1
			if position>3:
				window_start = position-3 
			if position+4 < window_end:
				window_end = position+4
			for pos in range(window_start,window_end):
				if spacyPosTags[pos][0] == word:
					engTag = spacyPosTags[pos][1]
					break

		file.write(str(lid)+'\t'+str(position)+'\t'+str(word)+'\t'+str(greekTag)+'\t'+str(engTag)+'\n')
	file.close()
	return "success"

parallelview_query = '''
	query verses($book:int, $chapter:int, $verse:int){
	parallel_verses(func: has(bible)){
	bible,
	books: ~belongsTo @filter(eq(bookNumber,$book)) {
	  book,
      bookNumber,
	  chapters:~belongsTo @filter(eq(chapter,$chapter)){
	  	chapter
	  	verses:~belongsTo @filter(eq(verse,$verse)){
        	verse,
	  		verseText:verseText,
	  		words: ~belongsTo(orderasc:position){
	  			position:position,
	  			word:word
	}	}  } } } 
	alignments(func: eq(bible,"Grk UGNT4 bible"))@normalize @cascade{
		~belongsTo @filter(eq(bookNumber,$book)){
		 book,
		 bookNumber,
		 ~belongsTo @filter(eq(chapter,$chapter)) {
		   chapter,
		   ~belongsTo @filter(eq(verse,$verse)){
		    verse
		    ~belongsTo{
		    	grkWord:word,
		    	grkPosition:position,
		    	~alignsTo{
		    		srcWord:word,
		    		srcPosition:position,
		    		belongsTo @filter(eq(verse,$verse)){
		    		 verse,
		    		 belongsTo @filter(eq(chapter,$chapter)){
		    		  chapter,
		    		  belongsTo @filter(eq(bookNumber,$book)){
		    		    book
		    		    belongsTo {
		    		    	srcBible:bible
	} } } } } } } } } }
	tws(func: eq(bible,"Grk UGNT4 bible"))@normalize @cascade{
		~belongsTo @filter(eq(bookNumber,$book)){
		 book,
		 bookNumber,
		 ~belongsTo @filter(eq(chapter,$chapter)) {
		   chapter,
		   ~belongsTo @filter(eq(verse,$verse)){
		    verse
		    ~belongsTo{
		    	grkWord:word,
		    	grkPosition:position,
		    	tw{
		    		desc:description
		    	}
	} } } } } 

	}
'''


@app.route('/dgraph/parallelview/<bcv>',methods=["GET"])
def parallel_bible(bcv):
	global graph_conn
	graph_conn = dGraph_conn()

	book = bcv[:-6]
	chapter = bcv[-6:-3]
	verse = bcv[-3:]
	# print('book:',book,",chapter:",chapter,',verse:',verse)

	variables = {"$book":str(book),
				"$chapter":str(chapter),
				"$verse":str(verse)}
	parallelview_res = graph_conn.query_data(parallelview_query,variables)
	alignments = parallelview_res['alignments']
	translationWords = parallelview_res['tws']
	output_content = ''
	for bible in parallelview_res['parallel_verses']:
		bible_val = bible['bible']
		if 'books' not in bible:
			continue
		for book in bible['books']:
			book_val = book['book']
			if 'chapters' not in book:
				continue
			for chapter in book['chapters']:
				chapter_val = chapter['chapter']
				if 'verses' not in chapter:
					continue
				for verse in chapter['verses']:
					verse_val = verse['verse']
					verseText = ''
					# if 'verseText' in verse:
					#	# This would show verseText with all punctuations
					# 	verseText = verse['verseText']
					if verseText == '':
						words = []
						for word in verse['words']:
							algmnt_classes = []
							infoBoxText = ''
							if bible_val == 'Grk UGNT4 bible':
								for i,algmnt in enumerate(alignments):
									if word['position'] == algmnt['grkPosition']:
										algmnt_classes.append("class=align"+str(algmnt['grkPosition']))
										for tw in translationWords:
											if tw['grkPosition']== algmnt['grkPosition']:
												infoBoxText += tw['tw']['desc'].replace("\"","&quot;")
												infoBoxText += tw['tw']['desc']
							else:
								for i,algmnt in enumerate(alignments):
									if algmnt['srcBible'] == bible_val and algmnt['srcPosition'] == word['position']:
										algmnt_classes.append("class=align"+str(algmnt['grkPosition']))
										for tw in translationWords:
											if tw['grkPosition']== algmnt['grkPosition']:
												infoBoxText += tw['tw']['desc'].replace("\"","&quot;")
												infoBoxText += tw['tw']['desc']
							display_word = word['word']
							words.append("<span "+" ".join(algmnt_classes)+" onmouseover=highlightAlignment(this.getAttribute('class'),this.getAttribute('data-info')) onmouseout=clearHighlight(this.getAttribute('class')) data-info=\""+infoBoxText+"\">"+display_word+"</span>")
						verseText = ' '.join(words)
					output_content += '<br>'+ bible_val+'<br>&nbsp;&nbsp;&nbsp;'+book_val+" "+str(chapter_val)+":"+str(verse_val)+"&nbsp;&nbsp;&nbsp;"+verseText+'<br>'

	return render_template('parallel_bible.html',content=output_content)

collection_query = '''
	query collection($name:string, $lang:string){
	collection(func: eq(collection,$name)) @filter(eq(language,$lang)) {
		uid: uid
	}	}
'''

bcv_query = '''
	query verse($bible:string, $book:string, $chapter:int, $verse:int){
	verse(func: eq(bible,$bible)) @normalize @cascade{
		~belongsTo @filter(eq(book,$book)){
		 ~belongsTo @filter(eq(chapter,$chapter)){
		 	~belongsTo @filter(eq(verse,$verse)){
		 		uid:uid
	}}}}}
'''

bcv_range_query = '''
	query verses($bible:string, $book:string, $chapter:int, $versestart:int, $verseend:int){
	verses(func: eq(bible,$bible)) @normalize @cascade{
		~belongsTo @filter(eq(book,$book)){
		 ~belongsTo @filter(eq(chapter,$chapter)){
		 	~belongsTo @filter(ge(verse,$versestart) AND le(verse,$verseend)){
		 		uid:uid
	}}}}}
'''

def findAllVerseNodesInRange(reference):
	global graph_conn
	refRangePattern = re.compile(r'(\d? *\w+) +(\d+) *: *(\d+)(-\d+)?')
	verse_uids = []
	if re.match(refRangePattern,reference):
		matchObjs = re.findall(refRangePattern,reference)
		bookname,chapter,startVerse,endVerse = matchObjs[0]
		if endVerse == "":
			endVerse = startVerse
		else:
			endVerse = endVerse.replace('-','')
		startVerse = int(startVerse)
		endVerse = int(endVerse)
		for v in range(startVerse,endVerse+1):
			variable = {'$bible':"Eng ULB bible",'$book':bookname, '$chapter':chapter, "$verse":str(v)}
			bcv_query_res = graph_conn.query_data(bcv_query,variable)
			if len(bcv_query_res['verse']) == 0:
				print("no verse found for ",variable)
			elif len(bcv_query_res['verse']) > 1:
				print("more than one verse found for ",variable)
			else:
				verse_uids.append(bcv_query_res['verse'][0]['uid'])
	else:
		print("************Couldn't parse the reference:",reference)
	# print(verse_uids)
	return verse_uids

def findAllVerseNodesInRange2(references):
	global graph_conn
	verse_uids = []
	refRangePattern = re.compile('from (I* *[A-Za-z ]+) *(\d+) *: *(\d+) to (I* *[A-Za-z ]+) *(\d+) *: *(\d+)')
	matchObjs = re.findall(refRangePattern,references)
	if len(matchObjs)==0:
		print("************Couldn't parse the reference:",reference)
	else:
		book1,chap1, ver1, book2, chap2, ver2  = matchObjs[0]
		book1 = book1.strip()
		book2 = book2.strip()
		if book1.startswith('II '):
			book1 = book1.replace('II ','2 ')
		elif book1.startswith('I '):
			book1 = book1.replace('I ','1 ')
		elif book1.startswith("Revelation"):
			book1 = "Revelation"
		if book2.startswith('II '):
			book2 = book2.replace('II ','2 ')
		elif book2.startswith('I '):
			book2 = book2.replace('I ','1 ')
		elif book2.startswith("Revelation"):
			book2 = "Revelation"
		print(book1,chap1, ver1, book2, chap2, ver2)
		if chap1 == chap2:
			variable = {'$bible':"Eng ULB bible",'$book':book1, '$chapter':chap1, "$versestart":ver1, "$verseend":ver2}
			bcv_range_query_res = graph_conn.query_data(bcv_range_query,variable)
			verse_uids = [item['uid'] for item in bcv_range_query_res['verses']]
			# print(bcv_range_query_res['verses'])
		else:
			variable = {'$bible':"Eng ULB bible",'$book':book1, '$chapter':chap1, "$versestart":ver1, "$verseend":'200'}
			bcv_range_query_res1 = graph_conn.query_data(bcv_range_query,variable)
			verse_uids = [item['uid'] for item in bcv_range_query_res1['verses']]
			variable = {'$bible':"Eng ULB bible",'$book':book1, '$chapter':chap2, "$versestart":'1', "$verseend":ver2}
			bcv_range_query_res2 = graph_conn.query_data(bcv_range_query,variable)
			verse_uids = verse_uids + [item['uid'] for item in bcv_range_query_res2['verses']]
	return verse_uids


@app.route('/dgraph/add-translationQuestions',methods=["GET"])
def addTransQuestions():
	global graph_conn
	graph_conn = dGraph_conn()
	tq_path = './Resources/translationQuestions/tQuestionsEnglish.csv'
	collection_name = 'Translation Questions'
	language = 'English'

	# create a collection if doesn't exist
	coll_node_uid = None
	coll_node_query_res = graph_conn.query_data(collection_query,{'$name':collection_name,'$lang':language})
	if len(coll_node_query_res['collection']) == 0:
		coll_node = { 'collection': collection_name, 'language':language	}
		coll_node_uid = graph_conn.create_data(coll_node)
		print("creating new node for ",collection_name)
	elif len(coll_node_query_res['collection']) > 1:
		print("Error!!! More than one node matched for ",collection_name)
	else:
		print(coll_node_query_res)
		coll_node_uid = coll_node_query_res['collection'][0]['uid']
	print("coll_node_uid:",coll_node_uid)

	count_for_test = 0
	with open(tq_path) as csv_file:
		csv_reader = csv.reader(csv_file, delimiter='\t')
		next(csv_reader)
		for row in csv_reader:
			sl_no,question,answer,references = row[0:4]
			sl_no = int(sl_no)
			# if sl_no < 57000 or sl_no > 58000:
			if sl_no < 41000 or sl_no > 45000:
				continue
			print(sl_no,question)
			verseuids =  findAllVerseNodesInRange(references)
			question_node = {
				'question':question,
				'answer':answer,
				'belongsTo':{'uid':coll_node_uid},
				'referenceVerse':[{'uid':uid} for uid in verseuids]
			} 
			question_node_uid = graph_conn.create_data(question_node)
	return "success"


@app.route('/dgraph/add-biblestories',methods=["GET"])
def addBibleStories():
	global graph_conn
	graph_conn = dGraph_conn()
	tq_path = './Resources/Bible Stories/BibleStriesEnglish.csv'
	collection_name = 'Bible Stories'
	language = 'English'

	# create a collection if doesn't exist
	coll_node_uid = None
	coll_node_query_res = graph_conn.query_data(collection_query,{'$name':collection_name,'$lang':language})
	if len(coll_node_query_res['collection']) == 0:
		coll_node = { 'collection': collection_name	, 'language':language}
		coll_node_uid = graph_conn.create_data(coll_node)
		print("creating new node for ",collection_name)
	elif len(coll_node_query_res['collection']) > 1:
		print("Error!!! More than one node matched for ",collection_name)
	else:
		print(coll_node_query_res)
		coll_node_uid = coll_node_query_res['collection'][0]['uid']
	print("coll_node_uid:",coll_node_uid)

	# count_for_test = 0
	# with open(tq_path) as csv_file:
	# 	csv_reader = csv.reader(csv_file, delimiter='\t')
	# 	next(csv_reader)
	# 	for row in csv_reader:
	# 		sl_no,title,story,references, images = row[0:5]
	# 		# if sl_no < 41000 or sl_no > 45000:
	# 		if int(sl_no) < 22 or int(sl_no) > 42:
	# 			continue
	# 		references = references.split(', ')
	# 		verse_uids = []
	# 		for ref_range in references:
	# 			verse_uids = verse_uids + findAllVerseNodesInRange2(ref_range)
	# 		print(sl_no,title)
	# 		story_node = {
	# 			'title':title,
	# 			'story':story,
	# 			'belongsTo':{'uid':coll_node_uid},
	# 			'referenceVerse':[{'uid':uid} for uid in verse_uids],
	# 			'images':images
	# 		} 
	# 		story_node_uid = graph_conn.create_data(story_node)
	addBibleStoryQuestions(coll_node_uid)
	return "success"

bStory_query = '''
	query story($colluid:string, $tit:string){
		story(func: eq(title,$tit)) @normalize @cascade{
			uid: uid,
			belongsTo @filter(uid($colluid)){
				collection
			}

	}}
'''

def addBibleStoryQuestions(collection_uid):
	global graph_conn
	path ='./Resources/Bible Stories/BibleStroyQuestions_English.csv'
	count = 0
	qa_pattern = re.compile(r'<<QUESTION>>: (.*)<<ANSWER>>: (.*)')

	with open(path) as csv_file:
		csv_reader = csv.reader(csv_file, delimiter='\t')
		next(csv_reader)
		for row in csv_reader:
			sl_no,title,summary,qa_list = row[0:4]

			variable = {"$colluid":collection_uid ,"$tit":title}
			bStory_query_res = graph_conn.query_data(bStory_query,variable)
			if len(bStory_query_res['story'])==1:
				count += 1
				print(count,title)
				story_uid = bStory_query_res['story'][0]['uid']
				qa_list = qa_list.split("|||")[:-1]
				qa_tuple_list = [re.findall(qa_pattern,qa) for qa in qa_list]
				# print(qa_tuple_list)

				summary_updation = { "uid": story_uid,
							 "summary": summary }
				graph_conn.create_data(summary_updation)
				for tup in qa_tuple_list:
					q = tup[0][0]
					a = tup[0][1]
					print(q)
					print(a)
					print("\n")
					question_node = {"uid":story_uid,
									"studyQuestion":{
										"question":q,
										"answer":a
									}}
					graph_conn.create_data(question_node)


def concept_finder(text):
	text_words = re.findall(r'\w+',text)
	text_words = [word.lower() for word in text_words]

	# all one-word, two_word and three_word slices
	possible_concepts = []
	possible_concepts += [' '.join(text_words[i:i+3]) for i in range(len(text_words)-2)]
	possible_concepts += [' '.join(text_words[i:i+2]) for i in range(len(text_words)-1)]
	possible_concepts += text_words
	for word in text_words:
		lemma = lemmatizer.lemmatize(word)
		if lemma not in possible_concepts and lemma not in stopWords:
			possible_concepts.append(lemma)
	for sw in list(stopWords)+["jesus"]:
		if sw in possible_concepts:
			possible_concepts.remove(sw)


	# find the available conceptnet UIRs.
	# if a multi-word concept is available, its component words should be exculded 
	# unless it is present again, separately in the text 
	possible_uris = [standardized_uri('en',phrase) for phrase in possible_concepts]
	valid_concepts = []
	added = []
	for uri in possible_uris:
			if uri in added:
				continue
			try:
				vec = en_cnembeddings.loc[uri]
				phrase = uri.replace('/c/en/','')
				valid_concepts.append((phrase,vec))
				# to remove component concepts
				words = phrase.split("_")
				phrase_components = []
				phrase_components += ['_'.join(words[i+2]) for i in range(len(words)-1)]
				phrase_components += words
				for comp in phrase_components:
					if '/c/en/'+comp in possible_uris:
						added.append('/c/en/'+comp)
			except Exception as e:
				# print("misshit at conceptnet:",uri)
				pass
	return valid_concepts

def concept_adder():
	graph_conn = dGraph_conn()
	node_type = 'title'
	node_type_query = '''
	query nodes($type:string){
		nodes(func:has(title)){
			uid,
			title,
	       '''+node_type+"Embeddings{ cn_term } } }"

	
	conceptNetNode_uid = None
	conceptnetNode_query_res = graph_conn.query_data(dictNode_query,{'$dict_name':'Conceptnet Numberbatch'})
	if len(conceptnetNode_query_res['dict']) == 0:
		print("created conceptnet dictionary node:",conceptNetNode_uid)
	elif len(conceptnetNode_query_res['dict']) > 1:
		print("matched multiple conceptnet nodes")
		return
	else:
		conceptNetNode_uid = conceptnetNode_query_res['dict'][0]['uid']
		print('found Conceptnet node')


	all_nodes_query_res = graph_conn.query_data(node_type_query,{"$type":node_type})
	all_nodes= all_nodes_query_res['nodes']
	for nod in all_nodes:
		# if node_type+"Embeddings" in nod:
		# 	print("Skipping")
		# 	continue
		# text = nod[node_type]
		text = nod["verseText"]

		# print(text)
		valid_concepts = concept_finder(text)
		for con in valid_concepts:
					# print("concept:",con[0])
					termEmbed_uid = None
					if node_type+"Embeddings" in nod:
						found_flag = False
						for embd in nod[node_type+"Embeddings"]:
							if embd['cn_term'] == con[0]:
								# print("skipping concept")
								found_flag = True
								break
						if found_flag:
							continue
					cnTerm_query_res = graph_conn.query_data(cnTerm_query,{'$term':con[0]})
					if len(cnTerm_query_res['terms'])==0 :
						termEmbed = {
							'cn_term':con[0],
							# 'embedding':term[1],
							'belongsTo': {'uid':conceptNetNode_uid}}
						termEmbed_uid = graph_conn.create_data(termEmbed)
						print("added embedding for: ",con[0])
					elif len(cnTerm_query_res['terms'])>1:
						print('multiple term nodes matched for:',con[0])
						return
					else:
						termEmbed_uid = cnTerm_query_res['terms'][0]['uid']

					nodeEmbedslink = {
						'uid': nod['uid'],
						node_type+'Embeddings': {'uid':termEmbed_uid}
					}
					print("adding concept link for ",con[0] )
					graph_conn.create_data(nodeEmbedslink)



if __name__ == '__main__':

	# app.run(host='0.0.0.0', port=5000, debug=True)
	
	# addTransQuestions()
	# addBibleStories()
	concept_adder()