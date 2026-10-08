"""Build notebooks/textual_analysis_sp500_ciz.ipynb from the legacy Textual Analysis page.

The page's prose and code are kept; screenshots become the cells that produce those outputs.
Changes to the code are limited to:
  - CRSP CIZ: S&P 500 membership from crsp_m_indexes.msp500list_v2, returns from
    crsp_m_stock.msf_v2, identifiers from stksecurityinfohist, CCM from crsp_m_ccm
    (same code as the S&P 500 Constituents page); comnam/ncusip/date become
    issuernm/cusip/mthcaldt downstream
  - gensim 4: the unused LdaMallet import is removed (gensim.models.wrappers no longer exists)
  - pandas 2+: DataFrame.append -> pd.concat
  - numpy: float(cosine_similarity(...)) -> cosine_similarity(...)[0, 0]
  - Doc2Vec gets a fixed seed and one worker so the published results are reproducible
  - lines wrapped to fit the site's code box

Run with the dedicated environment (.venv-nlp, kernel "fredasite-nlp").
"""
import os
import re
import nbformat as nbf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# The legacy page is kept as the source of prose and code
PAGE = os.path.join(ROOT, "notebooks", "originals", "textual-analysis-on-sp500-companies.qmd")
DEST = os.path.join(ROOT, "notebooks", "textual_analysis_sp500_ciz.ipynb")

src = open(PAGE).read()
body = src.split("---", 2)[2]
segments = re.split(r"(```python\n.*?```)", body, flags=re.S)
code_blocks = [s for s in segments if s.startswith("```python")]
assert len(code_blocks) == 27, len(code_blocks)


def code_of(seg):
    return seg[len("```python\n"):-3].rstrip("\n")


# ---- code replacements, by 1-based block number --------------------------------------
NEW = {}

NEW[2] = '''###################
# Connect to WRDS #
###################
conn=wrds.Connection()


### Get S&P500 Index Membership from CRSP
### I opt for the monthly frequency of the data,
### but one can choose to work with crsp.dsp500list_v2
### if more precise date range is needed.

sp500 = conn.raw_sql("""
    select distinct a.permno, a.mbrstartdt, a.mbrenddt,
           b.mthcaldt, b.mthret
    from crsp_m_indexes.msp500list_v2 as a,
         crsp_m_stock.msf_v2 as b
    where a.permno=b.permno
    and b.mthcaldt >= a.mbrstartdt and b.mthcaldt <= a.mbrenddt
    and b.mthcaldt between '01/01/2000' and '06/30/2026'
    order by b.mthcaldt, a.permno
    """, date_cols=['mbrstartdt', 'mbrenddt', 'mthcaldt'])'''

NEW[3] = '''### Add Other Company Identifiers from CRSP.STKSECURITYINFOHIST
### - You don't need this step if only PERMNO is required
### - This step aims to add TICKER, CUSIP, company name,
###   share type, primary exchange, SIC code and etc.

stkinfo = conn.raw_sql("""
    select distinct permno, issuernm, cusip, ticker,
           sharetype, securitytype, securitysubtype,
           primaryexch, siccd, secinfostartdt, secinfoenddt
    from crsp_m_stock.stksecurityinfohist
    """, date_cols=['secinfostartdt', 'secinfoenddt'])

# Merge with SP500 data
sp500_full = pd.merge(sp500, stkinfo, how='left', on='permno')

# Impose the date range restrictions
sp500_full = sp500_full.loc[
    (sp500_full.mthcaldt >= sp500_full.secinfostartdt)
    & (sp500_full.mthcaldt <= sp500_full.secinfoenddt)]'''

NEW[4] = '''### Add Compustat Identifiers
### - Link with Compustat's GVKEY and IID if need to work with
###   fundamental data
### - Linkage is done through crsp.ccmxpf_linktable

ccm=conn.raw_sql("""
    select distinct gvkey, liid as iid, lpermno as permno,
           linktype, linkprim, linkdt, linkenddt
    from crsp_m_ccm.ccmxpf_linktable
    where substr(linktype,1,1)='L'
    and (linkprim ='C' or linkprim='P')
    """, date_cols=['linkdt', 'linkenddt'])

# if linkenddt is missing then set to today date
ccm['linkenddt']=ccm['linkenddt'].fillna(pd.to_datetime('today'))

# Merge the CCM data with S&P500 data
# First just link by matching PERMNO
sp500ccm = pd.merge(sp500_full, ccm, how='left', on=['permno'])

# Then set link date bounds
sp500ccm = sp500ccm.loc[(sp500ccm['mthcaldt']>=sp500ccm['linkdt'])\\
                        &(sp500ccm['mthcaldt']<=sp500ccm['linkenddt'])]

# Rearrange columns for final output

sp500ccm = sp500ccm[['mthcaldt', 'permno', 'issuernm', 'cusip',
                     'ticker', 'sharetype', 'primaryexch', 'siccd',
                     'gvkey', 'iid', 'mbrstartdt', 'mbrenddt',
                     'mthret']]'''

# Small in-place edits: (block, old, new)
EDITS = [
    (1, "# Qingyi (Freda) Song Drechsler         #\n# Date: April 2021                      #",
        "# CRSP CIZ Format                       #\n# Qingyi (Freda) Song Drechsler         #\n"
        "# Date: April 2021                      #\n# Updated: October 2026                 #"),
    (1, "from gensim.models.wrappers import LdaMallet\n", ""),
    (5, "names = conn.raw_sql(\"\"\" select gvkey, cik, sic, naics, gind, gsubind from comp.names \"\"\")",
        "names = conn.raw_sql(\"\"\"\n    select gvkey, cik, sic, naics, gind, gsubind\n    from comp.names\n    \"\"\")"),
    (6, "compbus = conn.raw_sql(\"\"\" select gvkey, conm, cik, busdesc from comp.company \"\"\")",
        "compbus = conn.raw_sql(\"\"\"\n    select gvkey, conm, cik, busdesc from comp.company\n    \"\"\")"),
    (6, "ciqbus = conn.raw_sql(\"\"\" select a.*, b.gvkey, b.startdate, b.enddate\n"
        "                            from ciq.ciqbusinessdescription as a, \n"
        "                            ciq.wrds_gvkey as b\n"
        "                            where a.companyid = b.companyid \"\"\", date_cols = ['startdate', 'enddate'])",
        "ciqbus = conn.raw_sql(\"\"\"\n    select a.*, b.gvkey, b.startdate, b.enddate\n"
        "    from ciq.ciqbusinessdescription as a,\n    ciq.wrds_gvkey as b\n"
        "    where a.companyid = b.companyid\n    \"\"\", date_cols = ['startdate', 'enddate'])"),
    (7, "ciqbus_nodup = pd.merge(ciqbus, maxid, how = 'inner', on = ['gvkey', 'companyid'])",
        "ciqbus_nodup = pd.merge(ciqbus, maxid, how = 'inner',\n                        on = ['gvkey', 'companyid'])"),
    (8, "print('\\nShort business description from COMP:\\n', busdesc.iloc[1].busdesc )\n"
        "print('\\nLong business description from CIQ:\\n',  busdesc.iloc[1].businessdescription )",
        "# AAI Corporation (GVKEY 001002); selected by GVKEY, as row order can change\n"
        "aai = busdesc.loc[busdesc.gvkey == '001002'].iloc[0]\n"
        "print('\\nShort business description from COMP:\\n', aai.busdesc )\n"
        "print('\\nLong business description from CIQ:\\n',  aai.businessdescription )"),
    (9, "univ = sp500cik.loc[sp500cik.date=='12/31/2020'][['date', 'permno', 'comnam', 'ncusip', 'gvkey', 'iid', 'cik', 'ticker', 'sic', 'naics']]",
        "univ = sp500cik.loc[sp500cik.mthcaldt=='2020-12-31'][\n"
        "    ['mthcaldt', 'permno', 'issuernm', 'cusip', 'gvkey', 'iid',\n"
        "     'cik', 'ticker', 'sic', 'naics']]"),
    (9, "sp500busdesc = pd.merge(univ, busdesc[['gvkey', 'companyid', 'busdesc', 'businessdescription']], how = 'inner', on = ['gvkey'])",
        "sp500busdesc = pd.merge(univ, busdesc[['gvkey', 'companyid', 'busdesc',\n"
        "                                       'businessdescription']],\n"
        "                        how = 'inner', on = ['gvkey'])"),
    (10, "# Convert both short and long busindess description (busdesc, businessdescription) to list",
         "# Convert both short and long busindess description\n# (busdesc, businessdescription) to list"),
    (17, "for item, lst in list(bow_dict.items()):\n    _df = pd.DataFrame(lst.keys(), lst.values())\n"
         "    _df['comp_id'] = item\n    bow_df = bow_df.append(_df)",
         "for item, lst in list(bow_dict.items()):\n    _df = pd.DataFrame(lst.keys(), lst.values())\n"
         "    _df['comp_id'] = item\n    bow_df = pd.concat([bow_df, _df])"),
    (17, "bow_df = bow_df.reset_index().rename(columns={'index': 'freq', 0: 'word'})",
         "bow_df = bow_df.reset_index().rename(columns={'index': 'freq',\n                                              0: 'word'})"),
    (17, "sp500id = sp500busdesc[['permno', 'gvkey', 'iid', 'ticker']].reset_index().rename(columns={'index': 'comp_id'})",
         "sp500id = sp500busdesc[['permno', 'gvkey', 'iid', 'ticker']]\\\n"
         "    .reset_index().rename(columns={'index': 'comp_id'})"),
    (18, "totalcnt = bow_df.groupby('word')['freq'].sum().reset_index().sort_values(by=['freq'], ascending = False)",
         "totalcnt = bow_df.groupby('word')['freq'].sum().reset_index()\\\n"
         "    .sort_values(by=['freq'], ascending = False)"),
    (19, "print('Microsoft vs Disney:', \"{:.2f}\".format(float(cosine_similarity([vect_array[dis_pos]], [vect_array[msft_pos]]))))\n"
         "print('Disney vs Wells Fargo:',  \"{:.2f}\".format(float(cosine_similarity([vect_array[dis_pos]], [vect_array[wfc_pos]]))))\n"
         "print('Wells Fargo vs Citi:',    \"{:.2f}\".format(float(cosine_similarity([vect_array[c_pos]], [vect_array[wfc_pos]]))))",
         "def bow_pair(i, j):\n    return cosine_similarity([vect_array[i]], [vect_array[j]])[0, 0]\n\n"
         "print('Microsoft vs Disney:',   \"{:.2f}\".format(bow_pair(dis_pos, msft_pos)))\n"
         "print('Disney vs Wells Fargo:', \"{:.2f}\".format(bow_pair(dis_pos, wfc_pos)))\n"
         "print('Wells Fargo vs Citi:',   \"{:.2f}\".format(bow_pair(c_pos, wfc_pos)))"),
    (20, "            _tmp = {'comp1': ticker_lst[i],  # ticker for company i\n"
         "                    'comp2': ticker_lst[j],  # ticker for company j\n"
         "                    'bow_score': float(cosine_similarity([invect[i]], [invect[j]]))} # similarity score for pair (i,j)",
         "            _tmp = {'comp1': ticker_lst[i],  # ticker for company i\n"
         "                    'comp2': ticker_lst[j],  # ticker for company j\n"
         "                    # similarity score for pair (i,j)\n"
         "                    'bow_score': cosine_similarity([invect[i]],\n"
         "                                                   [invect[j]])[0, 0]}"),
    (21, "bow_score_df = bow_score_df.loc[bow_score_df.comp1 != bow_score_df.comp2].drop_duplicates()",
         "bow_score_df = bow_score_df.loc[bow_score_df.comp1 != bow_score_df.comp2]\\\n    .drop_duplicates()"),
    (21, "bow_score_df = bow_score_df.sort_values(by=['comp1', 'bow_score'], ascending = [True, False])",
         "bow_score_df = bow_score_df.sort_values(by=['comp1', 'bow_score'],\n"
         "                                        ascending = [True, False])"),
    (22, None, '''# For each company, keep the company with the highest cosine score
similar_comp_bow = bow_score_df.loc[
    bow_score_df.groupby('comp1')['bow_score'].idxmax()]

# merge back company identifier info
_ids = sp500busdesc[['issuernm', 'ticker', 'sic', 'naics']]
similar_comp_bow = pd.merge(similar_comp_bow, _ids, how = 'left',
                            left_on = 'comp1', right_on = 'ticker')
similar_comp_bow = pd.merge(similar_comp_bow, _ids, how = 'left',
                            left_on = 'comp2', right_on = 'ticker')
similar_comp_bow = similar_comp_bow.rename(columns={
    'comp2': 'comp_bow', 'issuernm_x':'issuernm1', 'issuernm_y':'issuernm_bow',
    'sic_x': 'sic1', 'sic_y':'sic_bow', 'naics_x':'naics1', 'naics_y':'naics_bow'})\\
    .drop(columns=['ticker_x', 'ticker_y'])
similar_comp_bow = similar_comp_bow[['comp1', 'issuernm1', 'sic1', 'naics1',
                                     'comp_bow', 'issuernm_bow', 'sic_bow',
                                     'naics_bow', 'bow_score']].drop_duplicates()'''),
    (24, "# Uses text_nonum as input as doc2vec approach doesn't require cleaning of stop words or lemmatization",
         "# Uses text_nonum as input as doc2vec approach doesn't require\n"
         "# cleaning of stop words or lemmatization"),
    (24, "tagged_text = [TaggedDocument(words=_d, tags=[str(i)]) for i, _d in enumerate(text_nonum)]",
         "tagged_text = [TaggedDocument(words=_d, tags=[str(i)])\n               for i, _d in enumerate(text_nonum)]"),
    (24, "model = Doc2Vec(dm=1, vector_size=40, min_count = 1)",
         "# fixed seed and a single worker make the results reproducible\n"
         "model = Doc2Vec(dm=1, vector_size=40, min_count = 1, seed=2021, workers=1)"),
    (24, "    model.train(tagged_text, epochs=model.epochs, total_examples=model.corpus_count)",
         "    model.train(tagged_text, epochs=model.epochs,\n                total_examples=model.corpus_count)"),
    (25, "print('Microsoft vs Disney:', \"{:.2f}\".format(model.wv.n_similarity(text_nostops[msft_pos], text_nostops[dis_pos])))\n"
         "print('Disney vs Wells Fargo:',  \"{:.2f}\".format(model.wv.n_similarity(text_nostops[dis_pos], text_nostops[wfc_pos])))\n"
         "print('Wells Fargo vs Citi:',    \"{:.2f}\".format(model.wv.n_similarity(text_nostops[wfc_pos], text_nostops[c_pos])))",
         "def d2v_pair(i, j):\n    return model.wv.n_similarity(text_nostops[i], text_nostops[j])\n\n"
         "print('Microsoft vs Disney:',   \"{:.2f}\".format(d2v_pair(msft_pos, dis_pos)))\n"
         "print('Disney vs Wells Fargo:', \"{:.2f}\".format(d2v_pair(dis_pos, wfc_pos)))\n"
         "print('Wells Fargo vs Citi:',   \"{:.2f}\".format(d2v_pair(wfc_pos, c_pos)))"),
    (26, "d2v_score_df = d2v_score_df.loc[d2v_score_df.comp1 != d2v_score_df.comp2].drop_duplicates()",
         "d2v_score_df = d2v_score_df.loc[d2v_score_df.comp1 != d2v_score_df.comp2]\\\n    .drop_duplicates()"),
    (26, "d2v_score_df = d2v_score_df.sort_values(by=['comp1', 'd2v_score'], ascending = [True, False])",
         "d2v_score_df = d2v_score_df.sort_values(by=['comp1', 'd2v_score'],\n"
         "                                        ascending = [True, False])"),
    (27, None, '''# For each company, keep the most similar company
similar_comp_d2v = d2v_score_df.loc[
    d2v_score_df.groupby('comp1')['d2v_score'].idxmax()]

similar_comp_d2v = pd.merge(similar_comp_d2v, _ids, how = 'left',
                            left_on = 'comp1', right_on = 'ticker')
similar_comp_d2v = pd.merge(similar_comp_d2v, _ids, how = 'left',
                            left_on = 'comp2', right_on = 'ticker')
similar_comp_d2v = similar_comp_d2v.rename(columns={
    'comp2': 'comp_d2v', 'issuernm_x':'issuernm1', 'issuernm_y':'issuernm_d2v',
    'sic_x': 'sic1', 'sic_y':'sic_d2v', 'naics_x':'naics1', 'naics_y':'naics_d2v'})\\
    .drop(columns=['ticker_x', 'ticker_y'])
similar_comp_d2v = similar_comp_d2v[['comp1', 'issuernm1', 'sic1', 'naics1',
                                     'comp_d2v', 'issuernm_d2v', 'sic_d2v',
                                     'naics_d2v', 'd2v_score']].drop_duplicates()'''),
]

# Cells that produce outputs which were screenshots without code on the page
IMAGE_CELLS = {
    2: "# GVKEY 003413 maps to more than one CIQ CompanyID\nciqbus.loc[ciqbus.gvkey == '003413']",
    6: "# Raw input text: Ralph Lauren's long business description\n"
       "rl_pos = sp500busdesc.loc[sp500busdesc.ticker == 'RL'].index.values[0]\n"
       "print(text_feed[rl_pos])",
    7: "# Cleaned output text\nprint(text_prep[rl_pos])",
    8: "# Most frequent words in Apple's business description\n"
       "bow_df.loc[bow_df.ticker == 'AAPL'][['word', 'freq', 'permno', 'gvkey', 'iid', 'ticker']]\\\n"
       "    .sort_values(by='freq', ascending=False).head(10)",
    13: "sample_d2v = similar_comp_d2v.loc[similar_comp_d2v.comp1.isin(company_ticker)]\n"
        "sample_d2v.style.format({'d2v_score': '{:.2f}'})",
    14: "# BOW and Doc2Vec results side by side\n"
        "compare = pd.merge(sample_bow[['comp1', 'issuernm1', 'comp_bow', 'bow_score']],\n"
        "                   sample_d2v[['comp1', 'comp_d2v', 'd2v_score']],\n"
        "                   how='inner', on='comp1')\n"
        "compare.style.format({'bow_score': '{:.2f}', 'd2v_score': '{:.2f}'})",
}

# Cited examples updated to the rerun results (user-approved); the sentences are otherwise unchanged
TEXT_EDITS = [
    ('the word "apple" appears 11 times, and the word "market" appears once',
     'the word "apple" appears 15 times, and the word "service" appears 6 times'),
    ("(e.g. GM vs F and or C vs JPM)", "(e.g. GM vs F and or V vs MA)"),
    ("(e.g. FB vs RMD or AMZN vs ATVI)", "(e.g. FB vs TWTR or AMZN vs ADBE)"),
    ("(e.g. ABT vs BDX, NCLH vs CCL, UAL vs AAL, WMT vs BBY)", "(e.g. ABT vs BDX, GM vs F, NCLH vs CCL, V vs MA)"),
    # LDA section was never written ("to be continued"); removed at the user's request
    ("- Similarity Based on Doc2Vec\n- Topic Classification using LDA", "- Similarity Based on Doc2Vec"),
    ("## part 7: topic classification using lda\n\nto be continued...", ""),
]
for o, _ in TEXT_EDITS:
    assert o in body, o

blocks = {}
for i, seg in enumerate(code_blocks, start=1):
    blocks[i] = NEW.get(i, code_of(seg))
for b, old, new in EDITS:
    if old is None:
        blocks[b] = new
    else:
        assert old in blocks[b], f"block {b}: {old[:60]!r}"
        blocks[b] = blocks[b].replace(old, new)

# Wrap lines to fit the site's code box (75 characters); code is unchanged otherwise
WRAP = [
    ("# Print one short and long version of the business description for inspection",
     "# Print one short and long version of the business description\n# for inspection"),
    ("# AAI Corporation (GVKEY 001002); selected by GVKEY, as row order can change",
     "# AAI Corporation (GVKEY 001002); selected by GVKEY,\n# as row order can change"),
    ("    nostop = [[word for word in doc if word not in stop_words] for doc in texts]",
     "    nostop = [[word for word in doc if word not in stop_words]\n              for doc in texts]"),
    ("bow_df.loc[bow_df.ticker == 'AAPL'][['word', 'freq', 'permno', 'gvkey', 'iid', 'ticker']]\\",
     "bow_df.loc[bow_df.ticker == 'AAPL'][['word', 'freq', 'permno',\n                                     'gvkey', 'iid', 'ticker']]\\"),
    ("### Examine word distribution across all company business descriptions (documents)",
     "### Examine word distribution across all company business\n### descriptions (documents)"),
    ("# Sort by comp1 then descending based on bow_score to find most similar companies",
     "# Sort by comp1 then descending based on bow_score\n# to find most similar companies"),
    ("sample_bow = similar_comp_bow.loc[similar_comp_bow.comp1.isin(company_ticker)]",
     "sample_bow = similar_comp_bow.loc[\n    similar_comp_bow.comp1.isin(company_ticker)]"),
    ("sample_d2v = similar_comp_d2v.loc[similar_comp_d2v.comp1.isin(company_ticker)]",
     "sample_d2v = similar_comp_d2v.loc[\n    similar_comp_d2v.comp1.isin(company_ticker)]"),
    ("                    'd2v_score':  model.wv.n_similarity(inlist[i], inlist[j]) }",
     "                    'd2v_score':  model.wv.n_similarity(inlist[i],\n                                                         inlist[j]) }"),
    ("compare = pd.merge(sample_bow[['comp1', 'issuernm1', 'comp_bow', 'bow_score']],",
     "compare = pd.merge(sample_bow[['comp1', 'issuernm1',\n                               'comp_bow', 'bow_score']],"),
]
for name in ("bow", "d2v"):
    WRAP += [
        (f"    'comp2': 'comp_{name}', 'issuernm_x':'issuernm1', 'issuernm_y':'issuernm_{name}',\n"
         f"    'sic_x': 'sic1', 'sic_y':'sic_{name}', 'naics_x':'naics1', 'naics_y':'naics_{name}'}})\\",
         f"    'comp2': 'comp_{name}',\n    'issuernm_x':'issuernm1', 'issuernm_y':'issuernm_{name}',\n"
         f"    'sic_x': 'sic1', 'sic_y':'sic_{name}',\n    'naics_x':'naics1', 'naics_y':'naics_{name}'}})\\"),
        (f"similar_comp_{name} = similar_comp_{name}[['comp1', 'issuernm1', 'sic1', 'naics1',\n"
         f"                                     'comp_{name}', 'issuernm_{name}', 'sic_{name}',\n"
         f"                                     'naics_{name}', '{name}_score']].drop_duplicates()",
         f"similar_comp_{name} = similar_comp_{name}[\n    ['comp1', 'issuernm1', 'sic1', 'naics1', 'comp_{name}',\n"
         f"     'issuernm_{name}', 'sic_{name}', 'naics_{name}', '{name}_score']]\\\n    .drop_duplicates()"),
    ]
for fn, a, b in (("bow_pair", "dis_pos, msft_pos", "dis_pos, wfc_pos"), ("d2v_pair", "msft_pos, dis_pos", "dis_pos, wfc_pos")):
    WRAP += [
        (f"print('Microsoft vs Disney:',   \"{{:.2f}}\".format({fn}({a})))",
         f"print('Microsoft vs Disney:',\n      \"{{:.2f}}\".format({fn}({a})))"),
        (f"print('Disney vs Wells Fargo:', \"{{:.2f}}\".format({fn}({b})))",
         f"print('Disney vs Wells Fargo:',\n      \"{{:.2f}}\".format({fn}({b})))"),
    ]

# ---- assemble cells ---------------------------------------------------------------------
cells = []
bi = 0
for seg in segments:
    if seg.startswith("```python"):
        bi += 1
        cells.append(nbf.v4.new_code_cell(blocks[bi]))
        continue
    text = seg
    text = re.sub(r'<div class="btn-row">.*?</div>\n*', "", text, flags=re.S)   # legacy "Full Code" link
    text = text.replace("crsp.dsp500list", "crsp.dsp500list_v2")
    for o, n in TEXT_EDITS:
        text = text.replace(o, n)
    parts = re.split(r"!\[\]\(\.\./images/textual-analysis_textual-analysis-on-sp500-companies/(\d+)\.png\)", text)
    for k, part in enumerate(parts):
        if k % 2 == 0:
            if part.strip():
                cells.append(nbf.v4.new_markdown_cell(part.strip()))
        else:
            img = int(part)
            if img in IMAGE_CELLS:
                cells.append(nbf.v4.new_code_cell(IMAGE_CELLS[img]))
            # other screenshots are the output of the preceding code cell

used = set()
for c in cells:
    if c.cell_type == "code":
        for k, (o, n) in enumerate(WRAP):
            if o in c.source:
                c.source = c.source.replace(o, n)
                used.add(k)
assert used == set(range(len(WRAP))), [WRAP[k][0][:50] for k in set(range(len(WRAP))) - used]
too_long = [l for c in cells if c.cell_type == "code" for l in c.source.splitlines() if len(l) > 75]
assert not too_long, too_long

nb = nbf.v4.new_notebook()
nb.cells = cells
nb.metadata["kernelspec"] = {"name": "fredasite-nlp", "display_name": "Python 3.12 (website NLP)", "language": "python"}
nbf.write(nb, DEST)
print(f"wrote {os.path.relpath(DEST, ROOT)}: {sum(c.cell_type == 'code' for c in cells)} code cells, "
      f"{sum(c.cell_type == 'markdown' for c in cells)} markdown cells")
