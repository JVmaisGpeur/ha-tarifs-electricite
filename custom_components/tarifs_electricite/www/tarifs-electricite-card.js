/*
 * Carte « Tarifs Électricité » — servie automatiquement par l'intégration.
 * type: custom:tarifs-electricite-card
 */
const VERSION_CARTE = "1.0.0";

const COULEURS_PERIODE = {
  HP: "#f57c00",
  HC: "#2e7d32",
  HSC: "#6a1b9a",
  BASE: "#1976d2",
  PERSO: "#00897b",
  WE: "#7cb342",
  WE_HC: "#558b2f",
};
const COULEURS_TEMPO = { bleu: "#1e88e5", blanc: "#eceff1", rouge: "#e53935" };
const NOMS_PERIODE = {
  HP: "Heures pleines",
  HC: "Heures creuses",
  HSC: "Heures super creuses",
  BASE: "Base",
  PERSO: "Période spéciale",
  WE: "Week-end",
  WE_HC: "Week-end heures creuses",
  DYN: "Prix dynamique",
};

// Vert → orange → rouge selon la place du prix entre min et max
function couleurPrix(prix, min, max) {
  if (prix === null || prix === undefined) return "var(--disabled-text-color, #bbb)";
  const r = max > min ? Math.min(1, Math.max(0, (prix - min) / (max - min))) : 0.5;
  const teinte = 120 - 120 * r;
  return `hsl(${teinte}, 65%, 45%)`;
}
const NOMS_SAISON = { hiver: "Hiver", ete: "Été", annee: "Toute l'année" };

const euro = (v, d = 4) =>
  v === null || v === undefined || isNaN(v)
    ? "—"
    : Number(v).toLocaleString("fr-FR", { minimumFractionDigits: d, maximumFractionDigits: d });

const heure = (iso) =>
  new Date(iso).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });

function dans(iso) {
  const ms = new Date(iso) - new Date();
  if (ms <= 0) return "maintenant";
  const min = Math.round(ms / 60000);
  const j = Math.floor(min / 1440);
  const h = Math.floor((min % 1440) / 60);
  const m = min % 60;
  if (j) return `dans ${j} j ${h} h`;
  if (h) return `dans ${h} h ${String(m).padStart(2, "0")}`;
  return `dans ${m} min`;
}

const dateFr = (iso) =>
  iso
    ? new Date(iso + "T12:00:00")
        .toLocaleDateString("fr-FR", { day: "numeric", month: "long", year: "numeric" })
        .replace(/^1 /, "1er ")
    : "Origine";
const pct = (v) => (v === null || v === undefined ? "" : `${v > 0 ? "+" : ""}${v.toLocaleString("fr-FR")} %`);

function jourCourt(iso) {
  const d = new Date(iso + "T12:00:00");
  const auj = new Date();
  auj.setHours(12, 0, 0, 0);
  const ecart = Math.round((d - auj) / 86400000);
  if (ecart === 0) return "Auj.";
  if (ecart === 1) return "Dem.";
  return d.toLocaleDateString("fr-FR", { weekday: "short", day: "numeric" });
}

class TarifsElectriciteCard extends HTMLElement {
  static getConfigElement() {
    return document.createElement("tarifs-electricite-card-editor");
  }

  static getStubConfig(hass) {
    const id =
      Object.keys(hass.states).find((e) => e.startsWith("sensor.tarif_electricite_prix_actuel")) ||
      "sensor.tarif_electricite_prix_actuel";
    return { entity: id };
  }

  setConfig(config) {
    this._config = {
      heures: 24,
      afficher_frise: false,
      afficher_tempo: false,
      afficher_grille: false,
      afficher_historique: false,
      afficher_suivi: false,
      ...config,
    };
    if (!this._config.entity) this._config.entity = "sensor.tarif_electricite_prix_actuel";
    this._dernier = null;
    this._rendu();
  }

  set hass(hass) {
    this._hass = hass;
    const st = hass.states[this._config?.entity];
    if (st !== this._dernier) {
      this._dernier = st;
      this._rendu();
    }
  }

  connectedCallback() {
    this._minuteur = setInterval(() => this._rendu(), 60000);
  }

  disconnectedCallback() {
    clearInterval(this._minuteur);
  }

  getCardSize() {
    return 5;
  }

  getGridOptions() {
    return { columns: 12, min_columns: 6, rows: "auto" };
  }

  _ouvrirReglages() {
    history.pushState(null, "", "/config/integrations/integration/tarifs_electricite");
    window.dispatchEvent(new CustomEvent("location-changed", { detail: { replace: false } }));
  }

  _plusInfo() {
    this.dispatchEvent(
      new CustomEvent("hass-more-info", {
        detail: { entityId: this._config.entity },
        bubbles: true,
        composed: true,
      })
    );
  }

  _frise(previsions) {
    const heures = Number(this._config.heures) || 24;
    if (!previsions?.length) return "";
    const debut = new Date(previsions[0].debut);
    const fin = new Date(debut.getTime() + heures * 3600000);
    const total = fin - debut;
    const connus = previsions.map((s) => s.prix).filter((p) => p !== null && p !== undefined);
    const pmin = Math.min(...connus);
    const pmax = Math.max(...connus);
    const blocs = previsions
      .filter((s) => new Date(s.debut) < fin)
      .map((s) => {
        const d = Math.max(new Date(s.debut), debut);
        const f = Math.min(new Date(s.fin), fin);
        const largeur = ((f - d) / total) * 100;
        let fond = COULEURS_PERIODE[s.periode] || "#888";
        let bord = "";
        if (s.periode === "DYN") {
          fond = couleurPrix(s.prix, pmin, pmax);
        } else if (s.jour_special) {
          bord = "background-image:repeating-linear-gradient(45deg,rgba(255,255,255,.35) 0 3px,transparent 3px 7px);box-shadow:inset 0 -3px 0 #c62828;";
        }
        if (s.couleur) {
          fond = COULEURS_TEMPO[s.couleur];
          if (s.periode === "HC") bord = "background-image:repeating-linear-gradient(135deg,rgba(0,0,0,.18) 0 4px,transparent 4px 8px);";
        } else if (s.periode !== "BASE" && s.prix === null) {
          fond = "var(--disabled-text-color, #bbb)";
        }
        const titre = `${s.libelle || NOMS_PERIODE[s.periode] || s.periode}${s.couleur ? " " + s.couleur : ""} · ${heure(s.debut)} → ${heure(s.fin)} · ${euro(s.prix)} €/kWh`;
        return `<div class="bloc" style="width:${largeur}%;background:${fond};${bord}" title="${titre}"></div>`;
      })
      .join("");
    const pas = heures > 24 ? 12 : 6;
    let reperes = "";
    const premier = new Date(debut);
    premier.setMinutes(0, 0, 0);
    premier.setHours(Math.ceil((debut.getHours() + (debut.getMinutes() ? 1 : 0)) / pas) * pas);
    for (let t = premier; t < fin; t = new Date(t.getTime() + pas * 3600000)) {
      const pos = ((t - debut) / total) * 100;
      if (pos < 12 || pos > 96) continue;
      reperes += `<span class="repere" style="left:${pos}%">${t.getHours()}h</span>`;
    }
    return `<div class="frise">${blocs}</div><div class="reperes"><span class="repere" style="left:0;transform:none">maint.</span>${reperes}</div>`;
  }

  _tempo(a) {
    const prev = a.tempo_previsions || [];
    if (!prev.length) {
      return `<div class="tempo vide">Couleurs Tempo indisponibles pour le moment.</div>`;
    }
    return `<div class="tempo">${prev
      .slice(0, 9)
      .map((p) => {
        let c = COULEURS_TEMPO[p.couleur] || "transparent";
        if (!p.confirmee && p.couleur === "blanc") c = "#90a4ae";
        const classe = p.confirmee ? "pastille" : "pastille prevue";
        return `<div class="jour"><span>${jourCourt(p.date)}</span><div class="${classe}" style="--c:${c}" title="${p.couleur || "inconnue"}${p.confirmee ? " (officielle)" : " (prévision)"}"></div></div>`;
      })
      .join("")}</div>
      <div class="legende">Plein : couleur officielle · Pointillé : prévision</div>`;
  }

  _grille(a) {
    const g = a.grille || {};
    const lignes = g.lignes || [];
    const cols = g.colonnes || [];
    if (!lignes.length) {
      if (a.type_offre === "dynamique")
        return `<div class="discret">Prix fixé heure par heure par le marché${a.source_prix ? ` (source : ${a.source_prix})` : ""}.</div>`;
      return "";
    }
    const entete = cols.map((c) => `<th>${c.nom}</th>`).join("");
    const corps = lignes
      .map((l) => {
        let lib = l.libelle;
        if (COULEURS_TEMPO[l.libelle])
          lib = `<span class="puce" style="--c:${COULEURS_TEMPO[l.libelle]}"></span>${l.libelle[0].toUpperCase()}${l.libelle.slice(1)}`;
        else if (l.special) lib = `<ha-icon class="petite" icon="mdi:calendar-alert"></ha-icon>${l.libelle}`;
        let actif;
        if (a.couleur_tempo) actif = l.libelle === a.couleur_tempo;
        else if (a.jour_special) actif = l.libelle === a.jour_special;
        else if (a.periode === "WE" || a.periode === "WE_HC") actif = l.libelle === "Week-end";
        else if (a.saison) actif = l.libelle.toLowerCase().startsWith(a.saison === "ete" ? "ét" : "hiv");
        else actif = lignes.indexOf(l) === 0;
        const periodeCol =
          a.periode === "WE" ? (cols.some((c) => c.cle === "HP") ? "HP" : "BASE")
          : a.periode === "WE_HC" ? "HC" : a.periode;
        const cellules = cols
          .map((c) => {
            const surligne = actif && c.cle === periodeCol ? ' class="actif"' : "";
            return `<td${surligne}>${l.prix[c.cle] === undefined ? "" : euro(l.prix[c.cle])}</td>`;
          })
          .join("");
        return `<tr><td class="lib">${lib}</td>${cellules}</tr>`;
      })
      .join("");
    const abo =
      a.abonnement_mensuel != null
        ? `<div class="abo">Abonnement : ${euro(a.abonnement_mensuel, 2)} €/mois${a.puissance_kva ? ` · ${a.puissance_kva} kVA` : ""}</div>`
        : "";
    return `<table><thead><tr><th></th>${entete}</tr></thead><tbody>${corps}</tbody></table>${abo}`;
  }

  _suivi(a) {
    const s = a.suivi;
    if (!s) return "";
    // L'abonnement est compté dans tous les montants : on le dit, et combien
    const avecAbo = a.abonnement_mensuel != null && a.abonnement_mensuel > 0;
    const dont = (v) => (avecAbo && v != null ? `<div class="dont">dont abonnement ${euro(v, 2)} €</div>` : "");
    if (s.etat !== "ok") {
      const msg = s.etat === "en_attente" ? "Calcul en cours…" : s.message || "Données indisponibles.";
      return `<div class="section"><h4>Ma consommation</h4><div class="discret">${msg}</div></div>`;
    }
    const tuile = (cle, titre) => {
      const p = s[cle] || {};
      const detail = avecAbo ? ` title="Énergie ${euro(p.cout_energie, 2)} € + abonnement ${euro(p.cout_abonnement, 2)} €"` : "";
      return `<div class="tuile"${detail}><span class="t-titre">${titre}</span><span class="t-val">${euro(p.total, 2)} €</span>
        <span class="t-kwh">${(p.kwh ?? 0).toLocaleString("fr-FR", { maximumFractionDigits: 1 })} kWh</span></div>`;
    };
    const e = s.estimation || {};
    let mensu = "";
    if (s.mode_paiement === "conso_reelle") {
      const f = s.facture;
      const FREQ = { 1: "tous les mois", 2: "tous les 2 mois", 3: "tous les 3 mois", 6: "tous les 6 mois", 12: "une fois par an" };
      if (f) {
        mensu += `<div class="mensualite">
          <div class="m-ligne"><span>Facture en cours <span class="discret">(depuis le ${dateFr(f.debut)})</span></span><b>${euro(f.montant_actuel, 2)} €</b></div>
          ${dont(f.abonnement_actuel)}
          <div class="m-ligne"><span>Estimée au ${dateFr(f.prochaine_facture)} <span class="discret">(dans ${Math.ceil(f.jours_restants)} j)</span></span><b>≈ ${euro(f.montant_estime, 2)} €</b></div>
          ${dont(f.abonnement_estime)}
          <div class="legende">Projection d'après les ${Math.min(14, Math.ceil(f.jours_ecoules))} derniers jours (${euro(f.cout_moyen_par_jour, 2)} €/jour hors abonnement).</div>
        </div>`;
      }
      if (e.cout_annuel_estime != null) {
        mensu += `<div class="m-ligne" style="margin-top:8px"><span>Coût annuel estimé <span class="discret">(${({ bonne: "fiable", moyenne: "fiabilité moyenne", faible: "peu fiable" })[e.fiabilite] || e.fiabilite})</span></span><b>${euro(e.cout_annuel_estime, 2)} €</b></div>
          ${dont(e.cout_abonnement_annuel)}
          <div class="legende">Soit ≈ ${euro(e.facture_moyenne_estimee, 2)} € par facture${avecAbo ? " (abonnement compris)" : ""} (${FREQ[s.frequence_mois] || ""}) · ${(e.consommation_annuelle_kwh ?? 0).toLocaleString("fr-FR")} kWh/an, d'après ${e.jours_de_donnees} jours${e.extrapole ? " extrapolés sur un an" : ""}</div>`;
      } else if (e.fiabilite === "insuffisante") {
        mensu += `<div class="legende">Estimation annuelle : il faut au moins 14 jours de consommation.</div>`;
      }
    } else if (e.mensualite_estimee != null) {
      const fiab = { bonne: "fiable", moyenne: "fiabilité moyenne", faible: "peu fiable" }[e.fiabilite] || e.fiabilite;
      let ecart = "";
      if (e.mensualite_fournisseur != null) {
        const cls = Math.abs(e.ecart_pct) <= 5 ? "ok" : e.ecart_mensuel > 0 ? "hausse" : "baisse";
        ecart = `<div class="m-ligne"><span>Prélevée par le fournisseur</span><span>${euro(e.mensualite_fournisseur, 2)} €</span></div>
          <div class="m-ligne"><span>Écart</span><span class="${cls}">${e.ecart_mensuel > 0 ? "+" : ""}${euro(e.ecart_mensuel, 2)} €/mois (${pct(e.ecart_pct)})</span></div>
          <div class="conseil">${e.conseil}</div>`;
      }
      mensu = `<div class="mensualite">
        <div class="m-ligne"><span>Mensualité estimée <span class="discret">(${e.prelevements_par_an} prélèvements, ${fiab})</span></span><b>${euro(e.mensualite_estimee, 2)} €</b></div>
        ${avecAbo ? `<div class="dont">abonnement compris (${euro(e.cout_abonnement_annuel / e.prelevements_par_an, 2)} € par prélèvement)</div>` : ""}
        ${ecart}
        <div class="legende">D'après ${e.jours_de_donnees} jours de consommation${e.extrapole ? " (extrapolés sur un an)" : ""} · ${(e.consommation_annuelle_kwh ?? 0).toLocaleString("fr-FR")} kWh/an · ${euro(e.cout_annuel_estime, 2)} €/an</div>
      </div>`;
    } else if (e.fiabilite === "insuffisante") {
      mensu = `<div class="legende">Mensualité : il faut au moins 14 jours de consommation (${e.jours_de_donnees || 0} pour l'instant).</div>`;
    }
    let solde = "";
    if (s.solde) {
      const v = s.solde.solde;
      solde = `<div class="m-ligne solde"><span>Depuis le ${dateFr(s.solde.depuis)} : payé ≈ ${euro(s.solde.paye_estime, 2)} €, consommé ${euro(s.solde.consomme, 2)} €</span>
        <span class="${v >= 0 ? "baisse" : "hausse"}">${v >= 0 ? "+" : ""}${euro(v, 2)} €</span></div>
        <div class="legende">${v >= 0 ? "Vous êtes en avance : remboursement probable." : "Vous êtes en retard : régularisation probable."}${s.solde.donnees_completes ? "" : " Historique du compteur incomplet sur la période."}</div>`;
    }
    const corrige = s.heures_corrigees
      ? `<div class="legende">${s.heures_corrigees} relevé(s) aberrant(s) du compteur ignoré(s) (saut d'index).</div>`
      : "";
    return `<div class="section"><h4>Ma consommation</h4>
      <div class="tuiles">${tuile("aujourdhui", "Aujourd'hui")}${tuile("semaine", "Semaine")}${tuile("mois", "Mois")}${tuile("annee", "Année")}</div>
      ${avecAbo ? `<div class="legende">Tous les montants comprennent l'abonnement (${euro(a.abonnement_mensuel, 2)} €/mois), au prorata de la période.</div>` : ""}
      ${mensu}${solde}${corrige}</div>`;
  }

  _historique(a) {
    const h = a.historique_prix || [];
    if (h.length < 2) return "";
    const NOMS = { en_cours: "En cours", prevue: "Prévue", passee: "Passée" };
    const lignes = h
      .slice()
      .reverse()
      .map((v) => {
        const vars = (v.variations || [])
          .map((x) => {
            const col = (a.grille?.colonnes || []).find((c) => c.cle === x.cle)?.nom || x.cle;
            const lib = x.libelle === "Abonnement" ? "Abonnement" : `${x.libelle === "Toute l'année" ? "" : x.libelle + " "}${col}`;
            const d = x.libelle === "Abonnement" ? 2 : 4;
            return `<div class="var"><span>${lib}</span><span>${euro(x.avant, d)} → <b>${euro(x.apres, d)}</b> <span class="${x.variation_pct > 0 ? "hausse" : "baisse"}">${pct(x.variation_pct)}</span></span></div>`;
          })
          .join("");
        const offre = v.offre !== a.offre ? `<div class="discret">${v.fournisseur} – ${v.offre}</div>` : "";
        return `<div class="version ${v.statut}">
          <div class="v-tete"><b>${v.date_effet ? "À partir du " + dateFr(v.date_effet) : "Grille d'origine"}</b>
          <span class="statut">${NOMS[v.statut]}</span></div>${offre}
          ${vars || (v.date_effet ? '<div class="discret">Aucun prix modifié</div>' : "")}</div>`;
      })
      .join("");
    return `<details class="historique"${this._histOuvert ? " open" : ""}><summary>Historique des prix (${h.length} grilles)</summary>${lignes}</details>`;
  }

  _joursSpeciaux(a) {
    const js = a.jours_speciaux;
    if (!js) return "";
    const puce = (quand, titre) => {
      const val = js[quand];
      const auto = js[`auto_${quand}`];
      const special = val && val !== "Normal";
      return `<div class="js ${special ? "special" : ""} ${auto ? "auto" : ""}" data-quand="${quand}"
        title="${auto ? "Suivi automatiquement depuis la source" : "Appuyez pour changer"}">
        <span class="js-titre">${titre}</span>
        <span class="js-val">${special ? "⚠ " : ""}${val}${auto ? ' <ha-icon class="petite" icon="mdi:link-variant"></ha-icon>' : ""}</span>
      </div>`;
    };
    const debut = js.debut_h ? `<div class="legende">Journée de ${js.debut_h} h à ${js.debut_h} h</div>` : "";
    return `<div class="js-ligne">${puce("aujourdhui", "Aujourd'hui")}${puce("demain", "Demain")}</div>${debut}`;
  }

  _changerJour(quand) {
    const js = this._hass?.states[this._config.entity]?.attributes?.jours_speciaux;
    if (!js || js[`auto_${quand}`]) return;
    const opts = js.options || [];
    const suivant = opts[(opts.indexOf(js[quand]) + 1) % opts.length];
    this._hass.callService("select", "select_option", {
      entity_id: `select.tarif_electricite_jour_special_${quand}`,
      option: suivant,
    });
  }

  _rendu() {
    if (!this._config) return;
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    const st = this._hass?.states[this._config.entity];
    if (!st) {
      this.shadowRoot.innerHTML = `<ha-card><div class="contenu">Entité introuvable : ${this._config.entity}<br>Ajoutez d'abord l'intégration « Tarifs Électricité ».</div></ha-card>`;
      return;
    }
    const a = st.attributes;
    const prix = st.state === "unknown" || st.state === "unavailable" ? null : Number(st.state);
    const periode = a.periode;
    let couleurPeriode = COULEURS_PERIODE[periode] || "#888";
    if (periode === "DYN") couleurPeriode = couleurPrix(prix, a.prix_min_24h, a.prix_max_24h);
    if (a.jour_special) couleurPeriode = "#c62828";
    const titre = this._config.titre || [a.fournisseur, a.offre].filter(Boolean).join(" · ");
    const estTempo = a.type_offre === "tempo";

    let badgeTempo = "";
    if (estTempo) {
      const c = a.couleur_tempo;
      badgeTempo = `<span class="badge tempo-badge" style="--c:${COULEURS_TEMPO[c] || "#999"}">Jour ${c || "inconnu"}</span>`;
    }

    let prochain = "";
    if (a.prochain_changement) {
      prochain = `<div class="prochain">
        <ha-icon icon="mdi:arrow-right-circle-outline"></ha-icon>
        <span><b>${a.prochaine_periode_libelle || NOMS_PERIODE[a.prochaine_periode] || a.prochaine_periode || ""}</b> à ${heure(a.prochain_changement)}
        <span class="discret">(${dans(a.prochain_changement)})</span> · ${euro(a.prochain_prix)} €/kWh</span></div>`;
    }

    // Min/max : seulement pour le prix dynamique
    const minmax =
      a.type_offre === "dynamique" && a.prix_min_24h != null
        ? `<div class="minmax">24 h : min ${euro(a.prix_min_24h)} · max ${euro(a.prix_max_24h)} €/kWh</div>`
        : "";

    this.shadowRoot.innerHTML = `
      <style>
        ha-card { overflow: hidden; }
        .entete { display:flex; align-items:center; gap:10px; padding:14px 16px 0; }
        .entete ha-icon { color: var(--primary-color); }
        .titre { flex:1; font-weight:600; font-size:1.05em; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
        .reglages { cursor:pointer; color: var(--secondary-text-color); --mdc-icon-size:20px; }
        .contenu { padding: 8px 16px 16px; }
        .principal { display:flex; align-items:baseline; gap:12px; flex-wrap:wrap; cursor:pointer; }
        .prix { font-size:2.4em; font-weight:700; line-height:1.1; }
        .unite { font-size:.4em; font-weight:400; color: var(--secondary-text-color); margin-left:4px; }
        .badge { padding:3px 10px; border-radius:12px; font-size:.85em; font-weight:600; color:#fff; background: var(--c); }
        .tempo-badge { color: #111; border:1px solid rgba(0,0,0,.2); }
        .prochain { display:flex; align-items:center; gap:6px; margin-top:6px; color: var(--primary-text-color); --mdc-icon-size:18px; }
        .discret, .minmax, .legende, .abo { color: var(--secondary-text-color); font-size:.85em; }
        .minmax { margin-top:2px; }
        .section { margin-top:14px; }
        .section h4 { margin:0 0 6px; font-size:.8em; text-transform:uppercase; letter-spacing:.05em; color: var(--secondary-text-color); font-weight:600; }
        .frise { display:flex; height:18px; border-radius:6px; overflow:hidden; background: var(--divider-color); }
        .bloc { height:100%; min-width:1px; }
        .reperes { position:relative; height:16px; font-size:.72em; color: var(--secondary-text-color); }
        .repere { position:absolute; top:2px; transform:translateX(-50%); white-space:nowrap; }
        .tempo { display:flex; gap:8px; flex-wrap:wrap; }
        .tempo.vide { color: var(--secondary-text-color); font-size:.9em; }
        .jour { display:flex; flex-direction:column; align-items:center; gap:3px; font-size:.75em; color: var(--secondary-text-color); min-width:34px; }
        .pastille { width:22px; height:22px; border-radius:50%; background: var(--c); border:1px solid rgba(0,0,0,.25); }
        .pastille.prevue { background: transparent; border:3px dashed var(--c); width:16px; height:16px; }
        .legende { margin-top:4px; font-size:.75em; }
        table { width:100%; border-collapse:collapse; font-size:.9em; }
        th { text-align:right; font-weight:600; color: var(--secondary-text-color); padding:2px 6px; }
        td { text-align:right; padding:4px 6px; border-top:1px solid var(--divider-color); font-variant-numeric: tabular-nums; }
        td.lib { text-align:left; }
        td.actif { font-weight:700; color: var(--primary-color); }
        .puce { display:inline-block; width:10px; height:10px; border-radius:50%; background: var(--c); border:1px solid rgba(0,0,0,.25); margin-right:6px; }
        .abo { margin-top:6px; }
        .bas { background:#2e7d32; }
        .evolution { display:flex; align-items:center; gap:6px; margin-top:8px; padding:6px 10px; border-radius:8px; background: rgba(3,169,244,.1); font-size:.9em; --mdc-icon-size:18px; }
        .hausse { color:#c62828; font-weight:600; }
        .baisse { color:#2e7d32; font-weight:600; }
        .historique { margin-top:12px; font-size:.9em; }
        .historique summary { cursor:pointer; color: var(--secondary-text-color); font-size:.85em; text-transform:uppercase; letter-spacing:.05em; font-weight:600; }
        .version { border-left:3px solid var(--divider-color); padding:4px 0 4px 10px; margin-top:8px; }
        .version.en_cours { border-left-color: var(--primary-color); }
        .version.prevue { border-left-color:#f57c00; }
        .v-tete { display:flex; justify-content:space-between; }
        .statut { font-size:.8em; color: var(--secondary-text-color); }
        .tuiles { display:grid; grid-template-columns:repeat(auto-fit, minmax(92px, 1fr)); gap:6px; }
        .tuile { background: var(--secondary-background-color, #f5f5f5); border-radius:10px; padding:6px 8px; display:flex; flex-direction:column; }
        .t-titre { font-size:.72em; color: var(--secondary-text-color); }
        .t-val { font-weight:700; font-size:1em; white-space:nowrap; }
        .t-kwh { font-size:.72em; color: var(--secondary-text-color); }
        .mensualite { margin-top:10px; }
        .m-ligne { display:flex; justify-content:space-between; align-items:baseline; gap:8px; margin-top:2px; }
        .m-ligne > :last-child { white-space:nowrap; }
        .m-ligne.solde { margin-top:8px; }
        .ok { color:#2e7d32; font-weight:600; }
        .dont { text-align:right; font-size:.75em; color: var(--secondary-text-color); margin-top:-2px; }
        .conseil { margin-top:4px; font-size:.85em; padding:6px 8px; border-radius:8px; background: rgba(255,152,0,.1); }
        .var { display:flex; justify-content:space-between; gap:8px; font-variant-numeric: tabular-nums; }
        .petite { --mdc-icon-size:14px; vertical-align:-2px; margin-right:4px; }
        .js-ligne { display:flex; gap:8px; }
        .js { flex:1; border:1px solid var(--divider-color); border-radius:10px; padding:6px 10px; cursor:pointer; display:flex; flex-direction:column; }
        .js.auto { cursor:default; }
        .js.special { border-color:#c62828; background:rgba(198,40,40,.08); }
        .js-titre { font-size:.75em; color: var(--secondary-text-color); }
        .js-val { font-weight:600; }
      </style>
      <ha-card>
        <div class="entete">
          <ha-icon icon="mdi:lightning-bolt"></ha-icon>
          <div class="titre">${titre || "Tarif électricité"}</div>
          <ha-icon class="reglages" icon="mdi:cog-outline" title="Modifier le contrat"></ha-icon>
        </div>
        <div class="contenu">
          <div class="principal">
            <div class="prix">${euro(prix)}<span class="unite">€/kWh</span></div>
            <span class="badge" style="--c:${couleurPeriode}">${a.periode_libelle || NOMS_PERIODE[periode] || periode || "—"}</span>
            ${badgeTempo}
            ${a.prix_bas ? '<span class="badge bas">Prix bas</span>' : ""}
          </div>
          ${prochain}
          ${minmax}
          ${a.evolution_prevue ? `<div class="evolution"><ha-icon icon="mdi:calendar-arrow-right"></ha-icon><span>Nouveaux prix le <b>${dateFr(a.evolution_prevue.date_effet)}</b>${a.evolution_prevue.variation_moyenne_pct != null ? ` · <span class="${a.evolution_prevue.variation_moyenne_pct > 0 ? "hausse" : "baisse"}">${pct(a.evolution_prevue.variation_moyenne_pct)}</span> en moyenne` : ""}</span></div>` : ""}
          ${this._config.afficher_frise ? `<div class="section"><h4>Prochaines ${this._config.heures} h</h4>${this._frise(a.previsions)}</div>` : ""}
          ${a.jours_speciaux ? `<div class="section"><h4>Jours spéciaux</h4>${this._joursSpeciaux(a)}</div>` : ""}
          ${a.type_offre === "dynamique" && a.previsions_disponibles === false ? '<div class="legende">La source ne publie pas les prix à venir : seule l\'heure en cours est connue.</div>' : ""}
          ${estTempo && this._config.afficher_tempo ? `<div class="section"><h4>Couleurs Tempo</h4>${this._tempo(a)}</div>` : ""}
          ${this._config.afficher_suivi ? this._suivi(a) : ""}
          ${this._config.afficher_grille ? `<div class="section"><h4>Grille tarifaire (€/kWh TTC)</h4>${this._grille(a)}</div>` : ""}
          ${this._config.afficher_historique ? this._historique(a) : ""}
        </div>
      </ha-card>`;
    this.shadowRoot.querySelector(".reglages")?.addEventListener("click", () => this._ouvrirReglages());
    this.shadowRoot.querySelector(".principal")?.addEventListener("click", () => this._plusInfo());
    this.shadowRoot.querySelector("details.historique")?.addEventListener("toggle", (ev) => {
      this._histOuvert = ev.target.open;
    });
    this.shadowRoot.querySelectorAll(".js").forEach((el) =>
      el.addEventListener("click", () => this._changerJour(el.dataset.quand))
    );
  }
}

const SCHEMA_EDITEUR = [
  {
    name: "entity",
    required: true,
    selector: { entity: { filter: [{ domain: "sensor", integration: "tarifs_electricite" }] } },
  },
  { name: "titre", selector: { text: {} } },
  {
    name: "heures",
    selector: {
      select: {
        mode: "dropdown",
        options: [
          { value: 12, label: "12 h" },
          { value: 24, label: "24 h" },
          { value: 48, label: "48 h" },
        ],
      },
    },
  },
  { name: "afficher_frise", selector: { boolean: {} } },
  { name: "afficher_tempo", selector: { boolean: {} } },
  { name: "afficher_grille", selector: { boolean: {} } },
  { name: "afficher_historique", selector: { boolean: {} } },
  { name: "afficher_suivi", selector: { boolean: {} } },
];
const LIBELLES = {
  entity: "Capteur « Prix actuel » du contrat",
  titre: "Titre (par défaut : fournisseur · offre)",
  heures: "Durée de la frise",
  afficher_frise: "Afficher la frise des prochaines heures",
  afficher_tempo: "Afficher les couleurs Tempo (offres Tempo)",
  afficher_grille: "Afficher la grille tarifaire",
  afficher_historique: "Afficher l'historique des prix",
  afficher_suivi: "Afficher ma consommation (coûts, mensualité)",
};

class TarifsElectriciteCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = { heures: 24, afficher_frise: false, afficher_tempo: false, afficher_grille: false, afficher_historique: false, afficher_suivi: false, ...config };
    this._rendu();
  }

  set hass(hass) {
    this._hass = hass;
    if (this._form) this._form.hass = hass;
  }

  _rendu() {
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.computeLabel = (s) => LIBELLES[s.name] || s.name;
      this._form.addEventListener("value-changed", (ev) => {
        this._config = ev.detail.value;
        this.dispatchEvent(
          new CustomEvent("config-changed", {
            detail: { config: this._config },
            bubbles: true,
            composed: true,
          })
        );
      });
      this.appendChild(this._form);
    }
    this._form.schema = SCHEMA_EDITEUR;
    this._form.data = this._config;
    if (this._hass) this._form.hass = this._hass;
  }
}

if (!customElements.get("tarifs-electricite-card")) {
  customElements.define("tarifs-electricite-card", TarifsElectriciteCard);
  customElements.define("tarifs-electricite-card-editor", TarifsElectriciteCardEditor);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "tarifs-electricite-card",
    name: "Tarifs Électricité",
    description: "Prix du kWh en cours, heures pleines/creuses, week-end, jours spéciaux, Tempo, prix dynamique et prévisions.",
    preview: true,
    documentationURL: "https://github.com/JVmaisGpeur/ha-tarifs-electricite",
  });
  console.info(`%c TARIFS-ELECTRICITE-CARD %c v${VERSION_CARTE} `, "background:#f57c00;color:#fff", "");
}
