-- Revised analysis: individual nonfarm/non-business labor income, nominal dollars.
-- The PID file establishes parentage. Cross-year records locate each person.
CREATE TABLE links AS
SELECT PID2 child_id68, PID3 child_pn,
       PID4 mother_id68, PID5 mother_pn, PID23 father_id68, PID24 father_pn
FROM pid WHERE PID4>0 AND PID5 BETWEEN 1 AND 995
           AND PID23>0 AND PID24 BETWEEN 1 AND 995;
-- Person number 999 means the parent was reported but identity is unclear.
CREATE UNIQUE INDEX link_child ON links(child_id68, child_pn);

-- Correctly assign a person's OWN income from their role, not family total.
CREATE TABLE personal AS
SELECT p.*, f.income_year,
       CASE WHEN p.relationship=10 AND p.sequence=1 THEN f.rp_earnings
            WHEN p.relationship IN (20,22) AND p.sequence=2 THEN f.sp_earnings
       END AS earnings
FROM person_year p
JOIN family_year f ON p.wave=f.wave AND p.family_id=f.family_id
WHERE p.sequence BETWEEN 1 AND 20;
CREATE UNIQUE INDEX personal_key ON personal(id68,pn,wave);

CREATE TABLE matched AS
SELECT l.*, ch.wave, ch.income_year,
       ch.age child_age, mo.age mother_age, fa.age father_age,
       mo.family_id mother_family_id, fa.family_id father_family_id,
       ch.earnings child_income, mo.earnings mother_income, fa.earnings father_income,
       mo.earnings+fa.earnings parent_income
FROM links l
JOIN personal ch ON ch.id68=l.child_id68 AND ch.pn=l.child_pn
JOIN personal mo ON mo.id68=l.mother_id68 AND mo.pn=l.mother_pn AND mo.wave=ch.wave
JOIN personal fa ON fa.id68=l.father_id68 AND fa.pn=l.father_pn AND fa.wave=ch.wave;

CREATE TABLE adult_observed AS
SELECT * FROM matched
WHERE child_age BETWEEN 19 AND 110
  AND mother_age BETWEEN 19 AND 110 AND father_age BETWEEN 19 AND 110
  AND child_income BETWEEN 0 AND 9999997
  AND mother_income BETWEEN 0 AND 9999997
  AND father_income BETWEEN 0 AND 9999997;

CREATE TABLE positive AS
SELECT * FROM adult_observed WHERE child_income>0 AND parent_income>0;

CREATE TABLE balanced AS
SELECT p.* FROM positive p
JOIN (SELECT child_id68,child_pn FROM positive
      GROUP BY child_id68,child_pn HAVING COUNT(DISTINCT wave)=4) b
USING(child_id68,child_pn);
CREATE UNIQUE INDEX balanced_key ON balanced(child_id68,child_pn,wave);

CREATE TABLE averaged AS
SELECT child_id68,child_pn,mother_id68,mother_pn,father_id68,father_pn,
       AVG(mother_income) mother_income, AVG(father_income) father_income,
       AVG(parent_income) parent_income,AVG(child_income) child_income,
       COUNT(*) n_years
FROM balanced
GROUP BY child_id68,child_pn,mother_id68,mother_pn,father_id68,father_pn
HAVING COUNT(*)=4;

-- Rank-rank bonus on the exact same positive balanced sample.
CREATE TABLE income_measures AS
SELECT CAST(income_year AS TEXT) measure,child_id68,child_pn,parent_income,child_income FROM balanced
UNION ALL
SELECT 'Four-year average',child_id68,child_pn,parent_income,child_income FROM averaged;

-- Midranks: average tied ranks, rescaled to percentiles centered in (0,100).
-- Parents are ranked across child observations; siblings retain equal parent ranks.
CREATE TABLE ranked AS
SELECT *,100.0*(RANK() OVER(PARTITION BY measure ORDER BY parent_income)
          +(COUNT(*) OVER(PARTITION BY measure,parent_income)-1)/2.0-0.5)
          /COUNT(*) OVER(PARTITION BY measure) parent_rank,
         100.0*(RANK() OVER(PARTITION BY measure ORDER BY child_income)
          +(COUNT(*) OVER(PARTITION BY measure,child_income)-1)/2.0-0.5)
          /COUNT(*) OVER(PARTITION BY measure) child_rank
FROM income_measures;
