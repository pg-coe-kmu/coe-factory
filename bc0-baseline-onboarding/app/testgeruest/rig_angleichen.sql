\set ON_ERROR_STOP on
ALTER TABLE public.anfrage_prozesse DROP CONSTRAINT IF EXISTS anfrage_prozesse_check;
ALTER TABLE public.anfrage_prozesse ADD CONSTRAINT ck_ap_tp_gehoert_kp CHECK (((sub_process_id IS NULL) OR ((sub_process_id)::text ~~ ((process_id)::text || '.%'::text)))) NOT VALID;
ALTER TABLE public.anfrage_prozesse ADD CONSTRAINT fk_ap_prozess FOREIGN KEY (company_id, process_id) REFERENCES public.ref_prozesse(company_id, process_id) ON DELETE CASCADE NOT VALID;
ALTER TABLE public.anfrage_prozesse ADD CONSTRAINT fk_ap_teilprozess FOREIGN KEY (company_id, sub_process_id) REFERENCES public.ref_teilprozesse(company_id, sub_process_id) ON DELETE CASCADE NOT VALID;
ALTER TABLE public.gate_ereignisse ADD CONSTRAINT gate_ereignisse_check1 CHECK (((ereignis <> 'uebergeben'::text) OR (paket_id IS NOT NULL))) NOT VALID;
ALTER TABLE public.gate_ereignisse ADD CONSTRAINT gate_ereignisse_benutzer_id_fkey FOREIGN KEY (benutzer_id) REFERENCES public.app_benutzer(benutzer_id) NOT VALID;
ALTER TABLE public.ref_anfragen DROP CONSTRAINT IF EXISTS ref_anfragen_check, DROP CONSTRAINT IF EXISTS ref_anfragen_check1;
ALTER TABLE public.ref_anfragen ADD CONSTRAINT fk_anfrage_steller FOREIGN KEY (company_id, steller_id) REFERENCES public.ref_personen(company_id, person_id) ON DELETE SET NULL NOT VALID;
DROP TRIGGER IF EXISTS teilprozess_eingefroren ON public.bitkom_bewertungen;
CREATE TRIGGER teilprozess_eingefroren BEFORE INSERT OR UPDATE ON public.bitkom_bewertungen FOR EACH ROW EXECUTE FUNCTION public.trg_teilprozess_eingefroren();
DROP TRIGGER IF EXISTS teilprozess_eingefroren ON public.ref_teilprozesse;
CREATE TRIGGER teilprozess_eingefroren BEFORE UPDATE ON public.ref_teilprozesse FOR EACH ROW EXECUTE FUNCTION public.trg_teilprozess_eingefroren();
DROP TRIGGER IF EXISTS historie ON public.ki_laufdaten;
