"""Presentation sessions over original GameItem/Candidate objects.

Cover choices are drafts. SD operations remain owned by the original workers.
"""
from dataclasses import dataclass, field
from math import ceil
from pathlib import Path
from PIL import Image
from ...core.models import Candidate
from ...core.image_quality import analyze_image
from ...core.dedupe import exact_image_hash
from ...services.cover_library import candidate_identity


@dataclass
class Session:
    query: str
    result_query: str
    page: int = 1
    results: list[str] = field(default_factory=list)
    local: list[str] = field(default_factory=list)
    a: str | None = None
    b: str | None = None
    tab: str = 'gallery'
    inspected: str | None = None
    history: list = field(default_factory=list)

    def navigate(self, tab, inspected=None):
        if self.tab != tab:self.history.append((self.tab,self.inspected))
        self.tab,self.inspected=tab,inspected

    def back(self):
        if not self.history:return False
        self.tab,self.inspected=self.history.pop()
        return True


@dataclass
class GameView:
    id: str
    real: object
    original: str
    cover: str | None = None
    choice: str | None = None
    proposal: str | None = None

    @property
    def title(self):return self.real.name
    @property
    def internal(self):return self.real.internal_name
    @property
    def region(self):return self.real.region
    @property
    def product(self):return self.real.product_id
    @property
    def slot(self):return None if self.real.pending_add else self.real.slot


class CoverStore:
    def __init__(self, window):
        self.window=window
        self.images={}
        self.sessions={}
        self.views={}
        self.candidate_objects={}
        self.pil_images={}

    @property
    def writable(self):
        return self.window.write_allowed and not self.window.operation_running()

    @property
    def readonly(self):return not self.window.write_allowed

    def view(self, real):
        identity=str(Path(self.window.root_path).resolve())+'|'+str(real.slot)+'|'+str(real.source_path or real.folder or '')
        game=self.views.get(identity)
        created=game is None or game.real is not real
        if created:
            game=GameView(identity,real,real.name)
            self.views[identity]=game
            self.sessions.pop(identity,None)
        if created and real.current_cover and not real.has_placeholder_cover:
            path=real.original_image or str(real.current_cover)
            if not Path(path).is_file():path=str(real.current_cover)
            key='current:'+identity+':'+path
            if key not in self.images:
                candidate=Candidate('current_cover',real.name,100,local_path=path,region=real.region)
                self.add_candidate(game,candidate,key=key)
            game.cover=key
        elif created:game.cover=None
        return game

    def session(self, game):
        return self.sessions.setdefault(game.id,Session(game.title,game.title))

    def add_candidate(self, game, candidate, image=None, *, key=None):
        key=key or 'candidate:'+candidate_identity(candidate)
        path=candidate.cached_path or candidate.local_path
        width,height=candidate.width,candidate.height
        failed=False
        try:
            if image is None and path:
                with Image.open(path) as source:image=source.convert('RGB')
            if image is not None:
                width,height=image.size
                self.pil_images[key]=image
        except (OSError,ValueError):failed=True
        self.candidate_objects[key]=candidate
        self.images[key]={'key':key,'title':candidate.title,'provider':candidate.source,'score':candidate.score,
          'region':candidate.region,'width':width,'height':height,'local_path':path,
          'contentId':exact_image_hash(image) if image is not None else candidate.exact_hash or key,'sourceFile':candidate.source_url or candidate.url or path,
          'duplicate_sources':list(candidate.duplicate_sources or []),'weak_match':candidate.weak_match,
          'quality_label':candidate.quality_label,'quality_score':candidate.quality_score,'failed':failed}
        return key

    def candidates(self, game):
        session=self.session(game)
        result=[]
        seen=set()
        for key in session.results+session.local:
            if key not in self.images:continue
            content=self.images[key].get('contentId',key)
            if content not in seen:seen.add(content);result.append(key)
        return result

    def page_keys(self, game):
        keys=self.candidates(game)
        session=self.session(game)
        pages=max(1,ceil(len(keys)/6))
        session.page=min(session.page,pages)
        return keys[(session.page-1)*6:session.page*6],pages

    def image(self, key):
        if key not in self.pil_images:
            with Image.open(self.images[key]['local_path']) as source:
                self.pil_images[key]=source.convert('RGB')
        return self.pil_images[key]

    def choose(self, game, key, confirmed=False):
        if not self.writable or game.real.pending_delete:return 'blocked'
        try:quality=analyze_image(self.image(key))
        except (OSError,ValueError):return 'decode_error'
        if not quality.accepted:return 'too_small'
        if quality.label=='Baja' and not confirmed:return 'confirm_low'
        item=self.images[key]
        current=self.images.get(game.cover,{})
        game.choice=None if item.get('contentId',key)==current.get('contentId',game.cover) else key
        return 'chosen' if game.choice else 'kept'

    def rename(self, game, name):
        if self.writable and name.strip():
            self.window.save_game_name(game.real,name.strip())
            return True
        return False

    def discard(self, game):
        if self.writable:game.choice=None

    def mark_pair(self, game, key):
        session=self.session(game)
        if session.a and self.images[session.a].get('contentId',session.a)!=self.images[key].get('contentId',key):
            session.b=key
            session.navigate('compare')
            return True
        session.a,session.b=key,None
        return False

    def plan(self):
        return [view for view in self.views.values() if view.choice and view.real in self.window.games]

    def clear(self):
        self.__init__(self.window)
