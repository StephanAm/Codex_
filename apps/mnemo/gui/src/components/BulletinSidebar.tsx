import { useState } from "react";
import { Instance } from "../api";
import { TagReferencePicker } from "@codex/ui";
import { InstancePicker } from "./InstancePicker";

export type BulletinGroupBy = "none" | "date" | "tag" | "reference" | "kind";

interface Props {
  noteCount: number;
  allTags: string[];
  allReferences: string[];
  instances: Instance[];
  timePeriod: string;
  dateFrom: string;
  dateTo: string;
  filterTags: string[];
  filterReferences: string[];
  filterInstanceIds: number[];
  groupBy: BulletinGroupBy;
  onTimePeriodChange: (p: string) => void;
  onDateFromChange: (d: string) => void;
  onDateToChange: (d: string) => void;
  onFilterTagsChange: (tags: string[]) => void;
  onFilterReferencesChange: (refs: string[]) => void;
  onFilterInstanceIdsChange: (ids: number[]) => void;
  onGroupByChange: (g: BulletinGroupBy) => void;
}

export function BulletinSidebar({
  noteCount, allTags, allReferences, instances,
  timePeriod, dateFrom, dateTo,
  filterTags, filterReferences, filterInstanceIds,
  groupBy,
  onTimePeriodChange, onDateFromChange, onDateToChange,
  onFilterTagsChange, onFilterReferencesChange, onFilterInstanceIdsChange,
  onGroupByChange,
}: Props) {
  const [filtersOpen, setFiltersOpen] = useState(true);

  const hasActiveFilter =
    timePeriod !== "today" ||
    filterTags.length > 0 ||
    filterReferences.length > 0 ||
    filterInstanceIds.length > 0;

  return (
    <div className="bulletin-sidebar">
      <div className="bulletin-sidebar-label">bulletin</div>

      <div className="note-list-filters">
        <button
          className={`note-list-filter-toggle${hasActiveFilter ? " note-list-filter-toggle--active" : ""}`}
          onClick={() => setFiltersOpen(o => !o)}
        >
          <span>filter</span>
          <span className="note-list-filter-arrow">{filtersOpen ? "▾" : "▸"}</span>
        </button>
        {filtersOpen && (
          <>
            <div className="filter-select-wrap">
              <select
                className="filter-select"
                value={timePeriod}
                onChange={e => onTimePeriodChange(e.target.value)}
              >
                <option value="all">Any time</option>
                <option value="today">Today</option>
                <option value="yesterday">Yesterday</option>
                <option value="thisweek">This week</option>
                <option value="thismonth">This month</option>
                <option value="7d">Last 7 days</option>
                <option value="30d">Last 30 days</option>
                <option value="3m">Last 3 months</option>
                <option value="1y">Last year</option>
                <option value="custom">Custom range…</option>
              </select>
              <span className="filter-select-arrow">▾</span>
            </div>
            {timePeriod === "custom" && (
              <div className="filter-date-range">
                <label className="filter-date-label">
                  From
                  <input
                    type="date"
                    className="filter-date-input"
                    value={dateFrom}
                    onChange={e => onDateFromChange(e.target.value)}
                  />
                </label>
                <label className="filter-date-label">
                  To
                  <input
                    type="date"
                    className="filter-date-input"
                    value={dateTo}
                    onChange={e => onDateToChange(e.target.value)}
                  />
                </label>
              </div>
            )}
            <TagReferencePicker
              label="Tags"
              prefix="#"
              kind="tag"
              allItems={allTags}
              selected={filterTags}
              onChange={onFilterTagsChange}
              allowNew={false}
              dropdownDir="down"
              compact
            />
            <TagReferencePicker
              label="Refs"
              prefix="@"
              kind="reference"
              allItems={allReferences}
              selected={filterReferences}
              onChange={onFilterReferencesChange}
              allowNew={false}
              dropdownDir="down"
              compact
            />
            {instances.length > 0 && (
              <InstancePicker
                instances={instances}
                selectedIds={filterInstanceIds}
                onChange={onFilterInstanceIdsChange}
              />
            )}
          </>
        )}
      </div>

      <div className="bulletin-structure">
        <div className="bulletin-structure-label">structure</div>
        <div className="filter-select-wrap">
          <select
            className="filter-select"
            value={groupBy}
            onChange={e => onGroupByChange(e.target.value as BulletinGroupBy)}
          >
            <option value="none">No grouping</option>
            <option value="date">Group by date</option>
            <option value="tag">Group by tag</option>
            <option value="reference">Group by reference</option>
            <option value="kind">Group by kind</option>
          </select>
          <span className="filter-select-arrow">▾</span>
        </div>
      </div>

      <div className="bulletin-note-count">
        {noteCount} {noteCount === 1 ? "note" : "notes"}
      </div>
    </div>
  );
}
