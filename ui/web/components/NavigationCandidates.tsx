import type { NavCandidate } from "../hooks/useJarvisStatus";
import "./NavigationCandidates.css";

interface NavigationCandidatesProps {
  candidates: NavCandidate[];
  onSelect: (candidate: NavCandidate) => void;
  onCancel: () => void;
}

export function NavigationCandidates({ candidates, onSelect, onCancel }: NavigationCandidatesProps) {
  return (
    <div className="nav-candidates">
      <div className="nav-candidates__header">
        <span className="nav-candidates__title">어느 곳으로 안내할까요?</span>
        <button className="nav-candidates__cancel" onClick={onCancel} type="button">
          ✕
        </button>
      </div>
      <ul className="nav-candidates__list">
        {candidates.map((c, i) => (
          <li key={`${c.lat}-${c.lng}`}>
            <button className="nav-candidates__item" onClick={() => onSelect(c)} type="button">
              <span className="nav-candidates__num">{i + 1}</span>
              <span className="nav-candidates__info">
                <span className="nav-candidates__name">{c.name}</span>
                <span className="nav-candidates__addr">{c.address || "주소 정보 없음"}</span>
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
