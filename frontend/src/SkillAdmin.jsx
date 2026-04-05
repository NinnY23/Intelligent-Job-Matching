import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import {
  getSkillsGraph,
  createSkill,
  updateSkill,
  addSkillHierarchyLink,
  removeSkillHierarchyLink,
  deleteSkill,
  createSkillAlias,
  deleteSkillAlias,
  seedSkills,
} from './api';
import SkillCombobox from './SkillCombobox';
import './SkillAdmin.css';

const pickDisplayName = (s) => s.display_name || s.slug;

const LIST_TRUNC = 20;

function HierarchyListCell({ items }) {
  const labels = (items || []).map((x) => x.label || x.slug);
  const full = labels.join(', ');
  if (!full) {
    return <span className="skill-admin-hierarchy-empty">—</span>;
  }
  const shown =
    full.length <= LIST_TRUNC ? full : `${full.slice(0, LIST_TRUNC)}…`;
  return (
    <span className="skill-admin-truncate-cell" title={full}>
      {shown}
    </span>
  );
}

export default function SkillAdmin() {
  const [skills, setSkills] = useState([]);
  const [aliases, setAliases] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const [newSkillName, setNewSkillName] = useState('');
  const [newParentSlug, setNewParentSlug] = useState('');
  const [selectedChildSlugs, setSelectedChildSlugs] = useState([]);
  const [childPickerText, setChildPickerText] = useState('');

  const [aliasInput, setAliasInput] = useState('');
  const [aliasCanonicalText, setAliasCanonicalText] = useState('');

  const [editingHierarchySlug, setEditingHierarchySlug] = useState(null);
  const [editLinkRelation, setEditLinkRelation] = useState('parent');
  const [editLinkPickerText, setEditLinkPickerText] = useState('');
  /** Which hierarchy tree to edit: same structure, `job` nodes are job titles/roles. */
  const [pageKind, setPageKind] = useState('skill');

  const addSkillFormRef = useRef(null);

  const skillsInView = useMemo(
    () => skills.filter((s) => (s.hierarchy_kind || 'skill') === pageKind),
    [skills, pageKind]
  );

  const aliasesInView = useMemo(
    () =>
      aliases.filter((a) => {
        const sk = skills.find((x) => x.slug === a.skill_slug);
        return (sk?.hierarchy_kind || 'skill') === pageKind;
      }),
    [aliases, skills, pageKind]
  );

  const load = useCallback(async () => {
    setError('');
    try {
      const data = await getSkillsGraph();
      const nextSkills = data.skills || [];
      setSkills(nextSkills);
      setAliases(data.aliases || []);
    } catch (e) {
      let msg = e.message || 'Failed to load skills graph';
      if (/unauthorized/i.test(msg)) {
        msg += ' Log out and sign in again.';
      }
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const showNotice = (msg) => {
    setNotice(msg);
    setTimeout(() => setNotice(''), 4000);
  };

  const skillsForChildPicker = useMemo(() => {
    const p = newParentSlug.trim().toLowerCase();
    return skillsInView.filter((s) => {
      if (selectedChildSlugs.includes(s.slug)) return false;
      if (
        p &&
        (s.slug.toLowerCase() === p ||
          (s.display_name || '').trim().toLowerCase() === p)
      ) {
        return false;
      }
      return true;
    });
  }, [skillsInView, selectedChildSlugs, newParentSlug]);

  const handleCreateSkill = async (e) => {
    e.preventDefault();
    setError('');
    try {
      const payload = {
        display_name: newSkillName.trim(),
        hierarchy_kind: pageKind,
      };
      if (newParentSlug.trim()) payload.parent_slug = newParentSlug.trim();
      const result = await createSkill(payload);
      const createdSlug = result.slug;
      const reparentErrors = [];
      if (createdSlug && selectedChildSlugs.length > 0) {
        for (const childSlug of selectedChildSlugs) {
          try {
            await addSkillHierarchyLink(createdSlug, {
              relation: 'child',
              target_slug: childSlug,
            });
          } catch (err) {
            reparentErrors.push(
              `${childSlug}: ${err.message || 'failed'}`
            );
          }
        }
      }
      setNewSkillName('');
      setNewParentSlug('');
      setSelectedChildSlugs([]);
      setChildPickerText('');
      await load();
      if (reparentErrors.length > 0) {
        setError(
          `Skill was created, but some children could not be attached: ${reparentErrors.join('; ')}`
        );
        showNotice('Skill added (check message for child attachment issues)');
      } else {
        showNotice(pageKind === 'job' ? 'Job node added' : 'Skill added');
      }
    } catch (e) {
      setError(e.message);
    }
  };

  const handleHierarchyKindChange = async (slug, nextKind) => {
    setError('');
    try {
      await updateSkill(slug, { hierarchy_kind: nextKind });
      await load();
      showNotice('Node type updated');
    } catch (e) {
      setError(e.message);
    }
  };

  const handleSeed = async () => {
    setError('');
    try {
      await seedSkills();
      await load();
      showNotice('Default skill tree seeded');
    } catch (e) {
      setError(e.message);
    }
  };

  const handleSaveHierarchyLink = async (skillSlug) => {
    setError('');
    const t = editLinkPickerText.trim();
    if (!t) {
      setError(`Pick or type a ${pageKind === 'job' ? 'job' : 'skill'} to link.`);
      return;
    }
    try {
      await addSkillHierarchyLink(skillSlug, {
        relation: editLinkRelation,
        target_slug: t,
      });
      setEditLinkPickerText('');
      await load();
      showNotice('Hierarchy link added');
    } catch (e) {
      setError(e.message);
    }
  };

  const handleRemoveHierarchyLink = async (skillSlug, relation, targetSlug) => {
    setError('');
    try {
      await removeSkillHierarchyLink(skillSlug, relation, targetSlug);
      await load();
      showNotice('Link removed');
    } catch (e) {
      setError(e.message);
    }
  };

  const openHierarchyEditor = (slug) => {
    setEditingHierarchySlug(slug);
    setEditLinkRelation('parent');
    setEditLinkPickerText('');
    setError('');
  };

  const closeHierarchyEditor = () => {
    setEditingHierarchySlug(null);
    setEditLinkPickerText('');
    setEditLinkRelation('parent');
  };

  const resetHierarchyAddRow = () => {
    setEditLinkPickerText('');
    setEditLinkRelation('parent');
  };

  const handleDeleteSkill = async (slug) => {
    const kindLabel = pageKind === 'job' ? 'job node' : 'skill';
    if (
      !window.confirm(
        `Delete ${kindLabel} "${slug}"? Remove all child links first (Edit → remove children).`
      )
    ) {
      return;
    }
    setError('');
    try {
      await deleteSkill(slug);
      await load();
      showNotice(pageKind === 'job' ? 'Job node deleted' : 'Skill deleted');
    } catch (e) {
      setError(e.message);
    }
  };

  const handleAddAlias = async (e) => {
    e.preventDefault();
    setError('');
    const canon = aliasCanonicalText.trim();
    if (!aliasInput.trim() || !canon) {
      setError('Enter both alias and canonical skill (name or slug).');
      return;
    }
    try {
      await createSkillAlias({
        alias_slug: aliasInput.trim(),
        skill_slug: canon,
      });
      setAliasInput('');
      setAliasCanonicalText('');
      await load();
      showNotice('Alias added');
    } catch (e) {
      setError(e.message);
    }
  };

  const handleDeleteAlias = async (id) => {
    setError('');
    try {
      await deleteSkillAlias(id);
      await load();
      showNotice('Alias removed');
    } catch (e) {
      setError(e.message);
    }
  };

  const scrollToAddSkill = () => {
    addSkillFormRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  const setParentAndFocusAddForm = (parentSlug) => {
    setNewParentSlug(parentSlug);
    scrollToAddSkill();
    const n = pageKind === 'job' ? 'job' : 'skill';
    showNotice(`Parent prefilled to "${parentSlug}". Enter the new ${n} name and submit.`);
  };

  const removeSelectedChild = (slug) => {
    setSelectedChildSlugs((prev) => prev.filter((s) => s !== slug));
  };

  const appendChildFromPick = (skill) => {
    setSelectedChildSlugs((prev) =>
      prev.includes(skill.slug) ? prev : [...prev, skill.slug]
    );
    setChildPickerText('');
  };

  if (loading) {
    return <div className="skill-admin-wrap">Loading skills…</div>;
  }

  return (
    <div className="skill-admin-wrap">
      <div className="skill-admin-header">
        <h2>{pageKind === 'job' ? 'Job hierarchy' : 'Skill hierarchy'}</h2>
        <div className="skill-admin-page-kind" role="group" aria-label="Hierarchy page type">
          <span className="skill-admin-page-kind-label">Page type</span>
          <div className="skill-admin-kind-toggle">
            <button
              type="button"
              className={pageKind === 'skill' ? 'is-active' : ''}
              onClick={() => setPageKind('skill')}
            >
              Skills
            </button>
            <button
              type="button"
              className={pageKind === 'job' ? 'is-active' : ''}
              onClick={() => setPageKind('job')}
            >
              Jobs
            </button>
          </div>
        </div>
        <p className="skill-admin-lead">
          One shared tree model: <strong>skills</strong> (tools, languages) and <strong>jobs</strong>{' '}
          (titles, roles). Switch page type to manage each list. Aliases and Prolog facts apply to both;
          edges can link within the same type. Seed loads default <strong>skill</strong> nodes only.
        </p>
        <button type="button" className="skill-admin-seed" onClick={handleSeed}>
          Load default tree (seed)
        </button>
      </div>

      <aside className="skill-admin-slug-help" aria-label="How skill names are stored">
        <h4 className="skill-admin-slug-help-title">Names and matching</h4>
        <p>
          You enter <strong>skill or job names</strong> depending on page type. The server derives a normalized id (a{' '}
          <strong>slug</strong>) from each name: lowercasing, stripping text in parentheses like{' '}
          <code>(v18)</code>, turning spaces into underscores, and keeping common symbols such as{' '}
          <code>+</code> <code>#</code> <code>.</code> and hyphens (e.g. <code>c++</code>, <code>c#</code>,{' '}
          <code>node.js</code>). Aliases can map several labels to one canonical skill.
        </p>
      </aside>

      {error && <div className="skill-admin-error">{error}</div>}
      {notice && <div className="skill-admin-notice">{notice}</div>}

      <section className="skill-admin-card" ref={addSkillFormRef}>
        <h3>Add a new {pageKind === 'job' ? 'job' : 'skill'}</h3>
        <p className="skill-admin-hint">
          Enter the <strong>new {pageKind === 'job' ? 'job' : 'skill'}&apos;s name</strong>. You can set one{' '}
          <strong>initial parent</strong> here (leave empty for a root). Use <strong>Edit</strong> on a row to
          add more parents or children. Optionally pick existing {pageKind === 'job' ? 'jobs' : 'skills'} as{' '}
          <strong>children</strong>. Comboboxes open on click; typing filters the list.
        </p>
        <form onSubmit={handleCreateSkill} className="skill-admin-form">
          <label>
            New {pageKind === 'job' ? 'job' : 'skill'} name *
            <SkillCombobox
              id="skill-admin-new-skill-name"
              skills={skillsInView}
              value={newSkillName}
              onChange={setNewSkillName}
              pickValue={pickDisplayName}
              placeholder="Type a new name or pick a label to start from"
              required
            />
          </label>
          <label>
            Initial parent (optional)
            <SkillCombobox
              id="skill-admin-new-parent"
              skills={skillsInView}
              value={newParentSlug}
              onChange={setNewParentSlug}
              placeholder={pageKind === 'job' ? 'Empty = root job' : 'Empty = root skill'}
            />
          </label>
          <div className="skill-admin-field-group">
            <span className="skill-admin-field-label">
              Children (optional — existing {pageKind === 'job' ? 'jobs' : 'skills'})
            </span>
            <p className="skill-admin-sublabel">
              Pick from the list to attach existing nodes under the new one after it is created.
            </p>
            {selectedChildSlugs.length > 0 && (
              <ul className="skill-admin-chip-list" aria-label="Selected child skills">
                {selectedChildSlugs.map((slug) => {
                  const row = skillsInView.find((x) => x.slug === slug);
                  const label = row?.display_name || slug;
                  return (
                    <li key={slug} className="skill-admin-chip">
                      <span>{label}</span>
                      <button
                        type="button"
                        className="skill-admin-chip-remove"
                        onClick={() => removeSelectedChild(slug)}
                        aria-label={`Remove ${label}`}
                      >
                        ×
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
            <SkillCombobox
              id="skill-admin-new-children-pick"
              skills={skillsForChildPicker}
              value={childPickerText}
              onChange={setChildPickerText}
              onOptionPick={appendChildFromPick}
              placeholder={`Click and pick a ${pageKind === 'job' ? 'job' : 'skill'} to add as child`}
            />
          </div>
          <button type="submit" className="skill-admin-primary">
            Add {pageKind === 'job' ? 'job' : 'skill'}
          </button>
        </form>
      </section>

      <section className="skill-admin-card">
        <h3>Hierarchy ({pageKind === 'job' ? 'jobs' : 'skills'})</h3>
        <div className="skill-admin-table-wrap">
          <table className="skill-admin-table skill-admin-hierarchy-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Type</th>
                <th>Parents</th>
                <th>Children</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {skillsInView.map((s) => (
                <React.Fragment key={s.id}>
                  <tr>
                    <td>{s.display_name || '—'}</td>
                    <td>
                      <select
                        className="skill-admin-kind-select"
                        aria-label={`Type for ${s.slug}`}
                        value={s.hierarchy_kind || 'skill'}
                        onChange={(e) =>
                          handleHierarchyKindChange(s.slug, e.target.value)
                        }
                      >
                        <option value="skill">Skill</option>
                        <option value="job">Job</option>
                      </select>
                    </td>
                    <td>
                      <HierarchyListCell items={s.parents} />
                    </td>
                    <td>
                      <HierarchyListCell items={s.children} />
                    </td>
                    <td className="skill-admin-actions">
                      <button
                        type="button"
                        className="skill-admin-small"
                        onClick={() =>
                          editingHierarchySlug === s.slug
                            ? closeHierarchyEditor()
                            : openHierarchyEditor(s.slug)
                        }
                      >
                        {editingHierarchySlug === s.slug ? 'Done' : 'Edit'}
                      </button>
                      <button
                        type="button"
                        className="skill-admin-small"
                        onClick={() => setParentAndFocusAddForm(s.slug)}
                        title={`Prefill initial parent for a new ${pageKind === 'job' ? 'job' : 'skill'}`}
                      >
                        New {pageKind === 'job' ? 'job' : 'skill'} under this
                      </button>
                      <button
                        type="button"
                        className="skill-admin-danger"
                        onClick={() => handleDeleteSkill(s.slug)}
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                  {editingHierarchySlug === s.slug && (
                    <tr className="skill-admin-hierarchy-expand-row">
                      <td colSpan={5} className="skill-admin-hierarchy-expand">
                        <div className="skill-admin-hierarchy-expand-inner">
                          <div className="skill-admin-hierarchy-current">
                            <div>
                              <span className="skill-admin-mini-label">Parents</span>
                              <ul
                                className="skill-admin-mini-chip-list"
                                aria-label="Parents of this skill"
                              >
                                {(s.parents || []).length === 0 ? (
                                  <li className="skill-admin-hierarchy-empty">None</li>
                                ) : (
                                  (s.parents || []).map((p) => (
                                    <li key={p.slug} className="skill-admin-mini-chip">
                                      <span>{p.label}</span>
                                      <button
                                        type="button"
                                        className="skill-admin-mini-chip-remove"
                                        onClick={() =>
                                          handleRemoveHierarchyLink(s.slug, 'parent', p.slug)
                                        }
                                        aria-label={`Remove parent ${p.label}`}
                                      >
                                        ×
                                      </button>
                                    </li>
                                  ))
                                )}
                              </ul>
                            </div>
                            <div>
                              <span className="skill-admin-mini-label">Children</span>
                              <ul
                                className="skill-admin-mini-chip-list"
                                aria-label="Children of this skill"
                              >
                                {(s.children || []).length === 0 ? (
                                  <li className="skill-admin-hierarchy-empty">None</li>
                                ) : (
                                  (s.children || []).map((c) => (
                                    <li key={c.slug} className="skill-admin-mini-chip">
                                      <span>{c.label}</span>
                                      <button
                                        type="button"
                                        className="skill-admin-mini-chip-remove"
                                        onClick={() =>
                                          handleRemoveHierarchyLink(s.slug, 'child', c.slug)
                                        }
                                        aria-label={`Remove child ${c.label}`}
                                      >
                                        ×
                                      </button>
                                    </li>
                                  ))
                                )}
                              </ul>
                            </div>
                          </div>
                          <div className="skill-admin-hierarchy-add-row">
                            <label className="skill-admin-relation-label">
                              <span className="skill-admin-sr-only">Link type</span>
                              <select
                                className="skill-admin-relation-select"
                                value={editLinkRelation}
                                onChange={(e) => setEditLinkRelation(e.target.value)}
                                aria-label="Link as parent or child"
                              >
                                <option value="parent">Linked skill is a parent of this one</option>
                                <option value="child">Linked skill is a child of this one</option>
                              </select>
                            </label>
                            <SkillCombobox
                              id={`skill-admin-hierarchy-pick-${s.slug}`}
                              skills={skillsInView.filter((x) => x.slug !== s.slug)}
                              value={editLinkPickerText}
                              onChange={setEditLinkPickerText}
                              placeholder={`Pick or type a ${pageKind === 'job' ? 'job' : 'skill'} name`}
                            />
                            <div className="skill-admin-hierarchy-add-actions">
                              <button
                                type="button"
                                className="skill-admin-small"
                                onClick={() => handleSaveHierarchyLink(s.slug)}
                              >
                                Save link
                              </button>
                              <button
                                type="button"
                                className="skill-admin-small"
                                onClick={resetHierarchyAddRow}
                              >
                                Cancel
                              </button>
                            </div>
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
            </tbody>
          </table>
          {skillsInView.length === 0 && (
            <p className="skill-admin-empty">
              No {pageKind === 'job' ? 'jobs' : 'skills'} yet.
              {pageKind === 'skill'
                ? ' Use seed or add skills above.'
                : ' Add jobs above or switch to Skills.'}
            </p>
          )}
        </div>
      </section>

      <section className="skill-admin-card">
        <h3>Aliases</h3>
        <p className="skill-admin-hint">
          Map alternate names (e.g. <code>js</code>) to a <strong>canonical</strong>{' '}
          {pageKind === 'job' ? 'job' : 'skill'} by name. The canonical entry must exist in the hierarchy
          table for this page type; the server normalizes names the same way as for new nodes.
        </p>
        <form onSubmit={handleAddAlias} className="skill-admin-form skill-admin-form-inline">
          <label>
            Alias text
            <input
              value={aliasInput}
              onChange={(e) => setAliasInput(e.target.value)}
              placeholder="e.g. JS"
              required
            />
          </label>
          <label>
            Canonical skill (type or pick)
            <SkillCombobox
              id="skill-admin-alias-canonical"
              skills={skillsInView}
              value={aliasCanonicalText}
              onChange={setAliasCanonicalText}
              placeholder="Click to list all — filter as you type"
              required
            />
          </label>
          <button
            type="submit"
            className="skill-admin-primary"
            disabled={!aliasInput.trim() || !aliasCanonicalText.trim()}
          >
            Add alias
          </button>
        </form>
        <ul className="skill-admin-alias-list">
          {aliasesInView.map((a) => (
            <li key={a.id}>
              <code>{a.alias_slug}</code>
              <span className="skill-admin-alias-arrow">→</span>
              <code>{a.skill_slug}</code>
              <button
                type="button"
                className="skill-admin-danger skill-admin-small"
                onClick={() => handleDeleteAlias(a.id)}
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
        {aliasesInView.length === 0 && (
          <p className="skill-admin-empty">No aliases for this type yet.</p>
        )}
      </section>
    </div>
  );
}
