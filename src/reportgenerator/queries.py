#!/bin/python3

from psycopg.rows import dict_row


class SyntheseQueries:
    """Synthese queries"""

    def __init__(self, conn, id_dataset):
        self.id_dataset = id_dataset
        self.conn = conn 

    def get_global_count(self):
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"""
                SELECT COUNT(*) AS count_data
                FROM gn_synthese.synthese
                WHERE id_dataset = {self.id_dataset}
            """
            )
            return cur.fetchone()


    def get_count_by_taxo_group(self):
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"""
                SELECT taxo_group, COUNT(*) count_data
                    FROM gn_synthese.synthese sy
                    JOIN src_lpodatas.t_c_synthese_extended tcse ON sy.id_synthese = tcse.id_synthese
                WHERE id_dataset = {self.id_dataset}
                GROUP BY taxo_group
            """
            )
            return cur.fetchall()


