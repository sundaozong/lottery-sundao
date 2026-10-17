from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from ..database import get_db
from ..schemas import ClusterIn, CollisionIn, EchoIn, MomentumIn, NeighborIn, ParityIn, PrimeIn, RepeatIn, RoadIn, SpanIn, SumIn
from ..services.affinity import affinity_stats
from ..services.analyze import analyze
from ..services.collision import collide, collide_records
from ..services.echo import find_echoes
from ..services.momentum import momentum_summary, score_momentum
from ..services.neighbor import neighbor_summary, score_neighbor
from ..services.repeat import repeat_pulse, score_repeat
from ..services.cluster import cluster_summary, score_cluster
from ..services.road import road_summary, score_road
from ..services.span import score_span, span_summary
from ..services.parity import parity_summary, score_parity
from ..services.prime import prime_summary, score_prime
from ..services.sum_pulse import score_sum, sum_summary
from ..services.shape import shape_stats
from ..services.seed import ensure_seed
from ..lotteries import normalize_type

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


@router.get("/{lottery_type}/repeat")
def get_repeat(
    lottery_type: str,
    limit: int = Query(80, ge=5, le=200),
    db: Session = Depends(get_db),
):
    ensure_seed(db)
    try:
        return repeat_pulse(db, normalize_type(lottery_type), limit=limit)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/{lottery_type}/repeat")
def post_repeat(lottery_type: str, body: RepeatIn, db: Session = Depends(get_db)):
    ensure_seed(db)
    try:
        return score_repeat(
            db,
            normalize_type(lottery_type),
            body.main,
            body.special,
            limit=body.limit,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/{lottery_type}/momentum")
def get_momentum(
    lottery_type: str,
    limit: int = Query(80, ge=5, le=200),
    short: int = Query(10, ge=5, le=30),
    long: int = Query(50, ge=20, le=200),
    db: Session = Depends(get_db),
):
    ensure_seed(db)
    try:
        return momentum_summary(
            db,
            normalize_type(lottery_type),
            limit=limit,
            short=short,
            long=long,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/{lottery_type}/momentum")
def post_momentum(lottery_type: str, body: MomentumIn, db: Session = Depends(get_db)):
    ensure_seed(db)
    try:
        return score_momentum(
            db,
            normalize_type(lottery_type),
            body.main,
            body.special,
            limit=body.limit,
            short=body.short,
            long=body.long,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/{lottery_type}/neighbor")
def get_neighbor(
    lottery_type: str,
    limit: int = Query(80, ge=5, le=200),
    horizon: int = Query(3, ge=1, le=10),
    db: Session = Depends(get_db),
):
    ensure_seed(db)
    try:
        return neighbor_summary(db, normalize_type(lottery_type), limit=limit, horizon=horizon)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/{lottery_type}/neighbor")
def post_neighbor(lottery_type: str, body: NeighborIn, db: Session = Depends(get_db)):
    ensure_seed(db)
    try:
        return score_neighbor(
            db,
            normalize_type(lottery_type),
            body.main,
            body.special,
            limit=body.limit,
            horizon=body.horizon,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/{lottery_type}/span")
def get_span(
    lottery_type: str,
    limit: int = Query(80, ge=5, le=200),
    short: int = Query(10, ge=5, le=30),
    long: int = Query(50, ge=20, le=200),
    db: Session = Depends(get_db),
):
    ensure_seed(db)
    try:
        return span_summary(
            db,
            normalize_type(lottery_type),
            limit=limit,
            short=short,
            long=long,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/{lottery_type}/span")
def post_span(lottery_type: str, body: SpanIn, db: Session = Depends(get_db)):
    ensure_seed(db)
    try:
        return score_span(
            db,
            normalize_type(lottery_type),
            body.main,
            body.special,
            limit=body.limit,
            short=body.short,
            long=body.long,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/{lottery_type}/cluster")
def get_cluster(
    lottery_type: str,
    limit: int = Query(80, ge=5, le=200),
    short: int = Query(10, ge=5, le=30),
    long: int = Query(50, ge=20, le=200),
    db: Session = Depends(get_db),
):
    ensure_seed(db)
    try:
        return cluster_summary(
            db,
            normalize_type(lottery_type),
            limit=limit,
            short=short,
            long=long,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/{lottery_type}/cluster")
def post_cluster(lottery_type: str, body: ClusterIn, db: Session = Depends(get_db)):
    ensure_seed(db)
    try:
        return score_cluster(
            db,
            normalize_type(lottery_type),
            body.main,
            body.special,
            limit=body.limit,
            short=body.short,
            long=body.long,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/{lottery_type}/road")
def get_road(
    lottery_type: str,
    limit: int = Query(80, ge=5, le=200),
    short: int = Query(10, ge=5, le=30),
    long: int = Query(50, ge=20, le=200),
    db: Session = Depends(get_db),
):
    ensure_seed(db)
    try:
        return road_summary(
            db,
            normalize_type(lottery_type),
            limit=limit,
            short=short,
            long=long,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/{lottery_type}/road")
def post_road(lottery_type: str, body: RoadIn, db: Session = Depends(get_db)):
    ensure_seed(db)
    try:
        return score_road(
            db,
            normalize_type(lottery_type),
            body.main,
            body.special,
            limit=body.limit,
            short=body.short,
            long=body.long,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/{lottery_type}/sum")
def get_sum(
    lottery_type: str,
    limit: int = Query(80, ge=5, le=200),
    short: int = Query(10, ge=5, le=30),
    long: int = Query(50, ge=20, le=200),
    db: Session = Depends(get_db),
):
    ensure_seed(db)
    try:
        return sum_summary(
            db,
            normalize_type(lottery_type),
            limit=limit,
            short=short,
            long=long,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/{lottery_type}/sum/score")
def post_sum(lottery_type: str, body: SumIn, db: Session = Depends(get_db)):
    ensure_seed(db)
    try:
        return score_sum(
            db,
            normalize_type(lottery_type),
            body.main,
            body.special,
            limit=body.limit,
            short=body.short,
            long=body.long,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/{lottery_type}/parity")
def get_parity(
    lottery_type: str,
    limit: int = Query(80, ge=5, le=200),
    short: int = Query(10, ge=5, le=30),
    long: int = Query(50, ge=20, le=200),
    db: Session = Depends(get_db),
):
    ensure_seed(db)
    try:
        return parity_summary(
            db,
            normalize_type(lottery_type),
            limit=limit,
            short=short,
            long=long,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/{lottery_type}/parity/score")
def post_parity(lottery_type: str, body: ParityIn, db: Session = Depends(get_db)):
    ensure_seed(db)
    try:
        return score_parity(
            db,
            normalize_type(lottery_type),
            body.main,
            body.special,
            limit=body.limit,
            short=body.short,
            long=body.long,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/{lottery_type}/prime")
def get_prime(
    lottery_type: str,
    limit: int = Query(80, ge=5, le=200),
    short: int = Query(10, ge=5, le=30),
    long: int = Query(50, ge=20, le=200),
    db: Session = Depends(get_db),
):
    ensure_seed(db)
    try:
        return prime_summary(
            db,
            normalize_type(lottery_type),
            limit=limit,
            short=short,
            long=long,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/{lottery_type}/prime/score")
def post_prime(lottery_type: str, body: PrimeIn, db: Session = Depends(get_db)):
    ensure_seed(db)
    try:
        return score_prime(
            db,
            normalize_type(lottery_type),
            body.main,
            body.special,
            limit=body.limit,
            short=body.short,
            long=body.long,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/{lottery_type}/affinity")
def get_affinity(
    lottery_type: str,
    limit: int = Query(50, ge=5, le=200),
    seed: str | None = Query(None),
    db: Session = Depends(get_db),
):
    ensure_seed(db)
    try:
        return affinity_stats(db, normalize_type(lottery_type), limit=limit, seed=seed)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/{lottery_type}/shape")
def get_shape(
    lottery_type: str,
    limit: int = Query(50, ge=5, le=200),
    db: Session = Depends(get_db),
):
    ensure_seed(db)
    try:
        return shape_stats(db, normalize_type(lottery_type), limit=limit)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/{lottery_type}/collision")
def post_collision(lottery_type: str, body: CollisionIn, db: Session = Depends(get_db)):
    ensure_seed(db)
    try:
        lottery = normalize_type(lottery_type)
        if body.from_records:
            return collide_records(db, lottery)
        return collide(lottery, [item.model_dump() for item in body.tickets])
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/{lottery_type}/echo")
def post_echo(lottery_type: str, body: EchoIn, db: Session = Depends(get_db)):
    ensure_seed(db)
    try:
        return find_echoes(
            db,
            normalize_type(lottery_type),
            body.main,
            body.special,
            limit=body.limit,
            top=body.top,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/{lottery_type}")
def get_analysis(
    lottery_type: str,
    limit: int = Query(50, ge=5, le=200),
    db: Session = Depends(get_db),
):
    ensure_seed(db)
    return analyze(db, normalize_type(lottery_type), limit=limit)
