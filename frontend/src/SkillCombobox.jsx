import React, { useMemo, useState, useRef, useEffect, useCallback } from 'react';

/**
 * @typedef {{ slug: string, display_name?: string | null }} SkillOption
 */

/**
 * @param {{
 *   value: string;
 *   onChange: (next: string) => void;
 *   skills: SkillOption[];
 *   placeholder?: string;
 *   id?: string;
 *   required?: boolean;
 *   disabled?: boolean;
 *   'aria-label'?: string;
 *   pickValue?: (skill: SkillOption) => string;
 *   className?: string;
 *   onOptionPick?: (skill: SkillOption) => void;
 * }} props
 */
export default function SkillCombobox({
  value,
  onChange,
  skills,
  placeholder = '',
  id,
  required = false,
  disabled = false,
  'aria-label': ariaLabel,
  pickValue = (s) => s.slug,
  className = '',
  onOptionPick,
}) {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef(null);

  const filtered = useMemo(() => {
    const q = value.trim().toLowerCase();
    if (!q) return skills;
    return skills.filter((s) => {
      const dn = (s.display_name || '').toLowerCase();
      return s.slug.toLowerCase().includes(q) || dn.includes(q);
    });
  }, [skills, value]);

  const close = useCallback(() => setOpen(false), []);

  useEffect(() => {
    const onDoc = (e) => {
      if (!wrapRef.current?.contains(e.target)) close();
    };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, [close]);

  const pick = useCallback(
    (skill) => {
      if (onOptionPick) {
        onOptionPick(skill);
      } else {
        onChange(pickValue(skill));
      }
      setOpen(false);
    },
    [onChange, pickValue, onOptionPick]
  );

  return (
    <div className={`skill-admin-combobox ${className}`.trim()} ref={wrapRef}>
      <input
        id={id}
        type="text"
        className="skill-admin-combobox-input"
        value={value}
        onChange={(e) => {
          onChange(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onClick={() => setOpen(true)}
        placeholder={placeholder}
        required={required}
        disabled={disabled}
        autoComplete="off"
        aria-expanded={open}
        aria-haspopup="listbox"
        aria-controls={id ? `${id}-listbox` : undefined}
        aria-label={ariaLabel}
      />
      {open && !disabled && (
        <ul
          id={id ? `${id}-listbox` : undefined}
          className="skill-admin-combobox-list"
          role="listbox"
        >
          {skills.length === 0 ? (
            <li className="skill-admin-combobox-empty" role="presentation">
              No skills loaded yet.
            </li>
          ) : filtered.length === 0 ? (
            <li className="skill-admin-combobox-empty" role="presentation">
              No matching skills — keep typing or use a new value.
            </li>
          ) : (
            filtered.map((s) => (
              <li
                key={s.slug}
                role="option"
                className="skill-admin-combobox-option"
                onMouseDown={(e) => {
                  e.preventDefault();
                  pick(s);
                }}
              >
                <span className="skill-admin-combobox-option-primary">
                  {s.display_name || s.slug}
                </span>
                <code className="skill-admin-combobox-option-slug">{s.slug}</code>
              </li>
            ))
          )}
        </ul>
      )}
    </div>
  );
}
