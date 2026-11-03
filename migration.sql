-- Showcase baseline, applied together with the selected ORM tables in one transaction.
CREATE TABLE proposal (
 document_id uuid PRIMARY KEY REFERENCES document,
 fragment text NOT NULL, metric text NOT NULL, amount numeric NOT NULL, unit text NOT NULL
);
CREATE TABLE approval (
 document_id uuid PRIMARY KEY REFERENCES proposal,
 reviewer_id uuid NOT NULL REFERENCES entity, reviewed_at timestamptz NOT NULL
);
ALTER TABLE financial_fact ADD FOREIGN KEY (source_document_id) REFERENCES approval;
CREATE EXTENSION IF NOT EXISTS btree_gist WITH SCHEMA public;
ALTER TABLE financial_fact ADD CONSTRAINT disjoint_versions EXCLUDE USING gist
(financial_period_id WITH =, financial_metric_id WITH =, tstzrange(known_from, known_to, '[)') WITH &&);
ALTER TABLE financial_fact ADD CHECK (known_to IS NULL OR known_to > known_from);
CREATE TABLE frozen_input (
 digest text PRIMARY KEY, payload jsonb NOT NULL
);
CREATE FUNCTION immutable_row() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'immutable record'; END $$;
CREATE FUNCTION close_once() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP = 'UPDATE' AND OLD.known_to IS NULL AND NEW.known_to IS NOT NULL
 AND (to_jsonb(NEW) - 'known_to') = (to_jsonb(OLD) - 'known_to') THEN RETURN NEW; END IF;
 RAISE EXCEPTION 'financial history must be superseded';
END $$;
CREATE TRIGGER protect_fact BEFORE UPDATE OR DELETE ON financial_fact
FOR EACH ROW EXECUTE FUNCTION close_once();
CREATE TRIGGER protect_doc BEFORE UPDATE OR DELETE ON document FOR EACH ROW EXECUTE FUNCTION immutable_row();
CREATE TRIGGER protect_proposal BEFORE UPDATE OR DELETE ON proposal FOR EACH ROW EXECUTE FUNCTION immutable_row();
CREATE TRIGGER protect_approval BEFORE UPDATE OR DELETE ON approval FOR EACH ROW EXECUTE FUNCTION immutable_row();
CREATE TRIGGER protect_manifest BEFORE UPDATE OR DELETE ON frozen_input FOR EACH ROW EXECUTE FUNCTION immutable_row();
