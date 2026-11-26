package br.ufmg.dcc;

import org.junit.Test;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

public class CalendarioTest {
  @Test
  public void testeBissextoComum() {
    Calendario cal = new Calendario();
    assertTrue(cal.ehBissexto(2024));
    assertFalse(cal.ehBissexto(2023));
  }
}
