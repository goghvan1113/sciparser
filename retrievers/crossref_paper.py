import sys
import os
import warnings
import json
import requests
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from CACHE.cache_request import cached_get
from paperfetcher import snowballsearch
from retrievers.Publication import Document
from retry import retry

class CrossrefPaper(Document):
    def __init__(self, ref_obj, ref_type='title', **kwargs):
        super().__init__(ref_obj, **kwargs)
        self.ref_type = ref_type
        self._entity = None if ('entity' not in kwargs) else kwargs['entity']
        self.data = None
        self._fetch_data()

    @retry(tries=3, delay=2)
    def _fetch_data(self):
        """Fetch data from Crossref API"""
        url = "https://api.crossref.org/works"

        params = {
            "query.bibliographic": self.ref_obj,
            "mailto": "1663653541@qq.com"
        }
        response = cached_get(url, params=params)
        if response and response.status_code == 200:
            self.data = response.json()
        else:
            raise Exception(f"Request failed with status code {response.status_code if response else 'No response'}")

    @property
    def entity(self, max_tries=5):
        if self._entity is None:
            if self.ref_type == 'title':
                for i, matched_paper in enumerate(self.data['message']['items']):
                    if matched_paper['title'][0].lower().replace(" ", "") == self.ref_obj.lower().replace(" ", ""):
                        self._entity = matched_paper
                        return self._entity
                    if i >= max_tries or i == len(self.data['message']['items']) - 1:
                        warnings.warn("Haven't fetch anything from crossref.", UserWarning)
                        self._entity = False
                        return self._entity
        return self._entity

    def _get_from_entity(self, key, default=None):
        """Helper method to safely get values from entity"""
        if self.entity and isinstance(self.entity, dict):
            return self.entity.get(key, default)
        return default

    @property
    def title(self):
        return self._get_from_entity('title', [None])[0]

    @property
    def doi(self):
        return self._get_from_entity('DOI')

    @property
    def publication_date(self):
        created = self._get_from_entity('created', {})
        if created and 'date-parts' in created:
            date_parts = created['date-parts'][0]
            if len(date_parts) >= 3:
                return f"{date_parts[0]}-{date_parts[1]:02d}-{date_parts[2]:02d}"
        return None

    @property
    def authors(self):
        """
        The authors of this document.
        作者逻辑这部分可以后续加入作者的详细信息，比如作者的机构，作者的ORCID等
        """
        if self.data:
            return [{'given': author.get('given'), 'family': author.get('family')} for author in self.data['message']['items'][0]['author']]
        return None

    @property
    def publisher(self):
        """The publisher of this document."""
        return self._get_from_entity('publisher')

    @property
    def language(self):
        """The language this document is written in."""
        return self._get_from_entity('language')

    @property
    def publication_source(self):
        """The name of the publication source (i.e., journal name, conference name, etc.)"""
        return self._get_from_entity('container-title', [None])[0]

    @property
    def source_type(self):
        """The type of publication source (i.e., journal, conference proceedings, book, etc.)"""
        return self._get_from_entity('type')

    @property
    def keywords(self):
        """The keywords of this document. What exactly consistutes as keywords depends on the data source (author keywords, generated keywords, topic categories), but is should be a list of strings."""
        return None  # Crossref API does not provide keywords directly

    @property
    def abstract(self):
        """The abstract of this document."""
        return None  # Crossref API does not provide abstract directly

    @property
    def citation_count(self):
        """The number of citations that this document received."""
        return self._get_from_entity('is-referenced-by-count')

    @property
    def references(self):
        """The list of other documents that are cited by this document."""
        if self.data:
            return [{'key': ref['key'], 'unstructured': ref.get('unstructured'), 'DOI': ref.get('DOI')} for ref in self.data['message']['items'][0]['reference']]
        return None

    @property
    def pub_url(self):
        """The URL of the document."""
        if self.data:
            return self.data['message']['items'][0]['link'][0]['URL']
        return None

    @property
    def field(self):
        """The field of the document."""
        return None  # Crossref API does not provide field directly


class COCIPaper:
    def __init__(self, cited_doi):
        self.cited_doi = cited_doi
        self._citing_dois = None
        self._citing_titles = None
        self.COCI_API_BASE = "https://opencitations.net/api/v1/citations"
        self.HTTP_HEADERS = {"authorization": "d3fd9c59-ab37-4c44-ae61-c0af33aea992"}

    @property
    def citing_dois(self):
        """Get DOIs of papers citing this paper through COCI API."""
        if self._citing_dois is None:
            self._citing_dois = self.get_citing_papers_api()
        return self._citing_dois

    @property
    def citing_titles(self):
        """Get titles of papers citing this paper."""
        if self._citing_titles is None:
            self._citing_titles = self._fetch_titles_from_dois()
        return self._citing_titles

    def _fetch_titles_from_dois(self):
        """通过DOI获取论文标题"""
        titles = []
        for doi in self.citing_dois:
            url = f"https://api.crossref.org/works/{doi}"
            try:
                response = cached_get(url)
                if response and response.status_code == 200:
                    data = response.json()
                    if 'title' in data['message']:
                        titles.append(data['message']['title'][0])
            except Exception as e:
                print(f"Error fetching title for DOI {doi}: {str(e)}")
        return titles

    def save_dois_to_file(self, file_path: str = "citing_dois.txt"):
        """将DOI列表保存到文件"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                for doi in self.citing_dois:
                    f.write(f"{doi}\n")
            return f"Successfully saved {len(self.citing_dois)} DOIs to {file_path}"
        except Exception as e:
            return f"Error saving DOIs to file: {str(e)}"

    @retry(tries=3, delay=2)
    def get_citing_papers_api(self):
        """Get citing papers using COCI API with retry and caching."""
        if not self.cited_doi:
            return []
        api_url = f"{self.COCI_API_BASE}/{self.cited_doi}"
        response = cached_get(api_url, headers=self.HTTP_HEADERS)
        if response and response.status_code == 200:
            data = response.json()
            return [item['citing'] for item in data if 'citing' in item]
        return []

    def get_citing_papers_paperfetcher(self):
        """Get citing papers using paperfetcher library."""
        if not self.cited_doi:
            return []
        search = snowballsearch.COCIForwardCitationSearch([self.cited_doi])
        search()
        doi_ds = search.get_DOIDataset()
        return doi_ds.to_df()['DOI'].tolist()


if __name__ == "__main__":
    # 1) Use CrossrefPaper to get the DOI by title
    query = "A survey on sentiment analysis of scientific citations"
    cr_paper = CrossrefPaper(ref_obj=query)
    print("Title:", cr_paper.title)
    print("Retrieved DOI from Crossref:", cr_paper.doi)

    # 2) Use COCIPaper with that DOI to fetch citing papers
    if cr_paper.doi:
        coci_paper = COCIPaper(cr_paper.doi)
        citing_dois = coci_paper.citing_dois
        print("\nCiting DOIs from COCI API:", citing_dois[:5], f"...(total: {len(citing_dois)})")

        # citing_pf = coci_paper.get_citing_papers_paperfetcher()
        # print("\nCiting DOIs from paperfetcher:", citing_pf[:5], f"...(total: {len(citing_pf)})")
