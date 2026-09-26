# -*- coding: utf-8 -*-
"""Barra de título própria — o que dá para conferir sem abrir janela.

O resto (arrastar, Snap, bordas, duplo clique) é o roteiro 2.3 do
TESTES.md, conferido na tela.
"""

import ctypes
import sys
import unittest

from sped_tables.interface import janela_custom as jc


class TestMenuDeSistema(unittest.TestCase):

    def test_itens_conforme_o_estado(self):
        solta = jc.itens_do_menu(False)
        self.assertFalse(solta[jc.SC_RESTORE])
        self.assertTrue(solta[jc.SC_MOVE] and solta[jc.SC_SIZE]
                        and solta[jc.SC_MAXIMIZE])
        cheia = jc.itens_do_menu(True)
        self.assertTrue(cheia[jc.SC_RESTORE])
        self.assertFalse(cheia[jc.SC_MOVE] or cheia[jc.SC_SIZE]
                         or cheia[jc.SC_MAXIMIZE])
        self.assertTrue(cheia[jc.SC_CLOSE] and cheia[jc.SC_MINIMIZE])

    @unittest.skipUnless(sys.platform == "win32", "Win32")
    def test_clique_direito_fora_da_barra_segue_o_padrao(self):
        """Só o clique direito na faixa da barra (HTCAPTION) abre o menu;
        nas bordas, o Windows trata como sempre."""
        abertos = []
        msg = jc.MSG()
        msg.message = jc.WM_NCRBUTTONUP
        msg.wParam = jc.HTLEFT
        original = jc._menu_de_sistema
        jc._menu_de_sistema = lambda *a: abertos.append(a)
        try:
            ptr = ctypes.addressof(msg)
            self.assertEqual(jc.tratar(None, ptr, 30), (False, 0))
            msg.wParam = jc.HTCAPTION
            msg.lParam = (200 << 16) | 100
            self.assertEqual(jc.tratar(None, ptr, 30), (True, 0))
        finally:
            jc._menu_de_sistema = original
        self.assertEqual(len(abertos), 1)
        self.assertEqual(abertos[0][1:], (100, 200))


if __name__ == "__main__":
    unittest.main()
